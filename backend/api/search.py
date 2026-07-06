from fastapi import APIRouter, Depends, HTTPException
import datetime
import logging
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.session import get_db, get_readonly_db
from db.models import Email, Attachment
from services.embedding import STORAGE_EMBEDDING_DIMENSION, fit_embedding_vector, generate_embeddings
from api.auth import AuthContext, get_auth_context
from services.exceptions import EmbeddingGenerationError
from services.llm_provider_selection import resolve_runtime_llm_provider

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
SEARCH_VECTOR_DIMENSIONS = STORAGE_EMBEDDING_DIMENSION

# Reciprocal-rank-fusion constant (standard default). Fusing by rank instead
# of raw scores avoids mixing incomparable scales (ts_rank_cd vs cosine
# distance), which the previous subtraction-based score suffered from.
RRF_K = 60


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class SearchResultItem(BaseModel):
    id: int
    source_message_id: str | None = None
    subject: str | None
    sender: str
    date: datetime.datetime
    snippet: str
    thread_id: str | None = None
    reply_count: int = 1
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]


def thread_group_key():
    normalized_thread_id = func.nullif(
        func.btrim(func.btrim(Email.thread_id), "<>"), ""
    )
    normalized_message_id = func.nullif(
        func.btrim(func.btrim(Email.message_id), "<>"), ""
    )
    return func.coalesce(normalized_thread_id, normalized_message_id)


def build_reply_counts_subquery(
    user_id: str | None = None, organization_id: str | None = None
):
    group_key = thread_group_key()
    statement = select(
        group_key.label("thread_key"),
        func.count(Email.id).label("reply_count"),
    ).select_from(Email)
    if user_id is not None:
        statement = statement.where(*Email.owner_filters(user_id, organization_id))
    return statement.group_by(group_key).subquery("thread_counts")


def _fts_match(text_column, query: str):
    return func.to_tsvector("english", text_column).op("@@")(
        func.plainto_tsquery("english", query)
    )


def _fts_rank(text_column, query: str):
    return func.ts_rank_cd(
        func.to_tsvector("english", text_column),
        func.plainto_tsquery("english", query),
    )


def build_lexical_email_stmt(query: str, owner_filters, candidate_limit: int):
    """FTS arm over email bodies: @@-gated so the GIN index applies."""
    return (
        select(Email.id, Email.body.label("content"))
        .where(*owner_filters, _fts_match(Email.body, query))
        .order_by(_fts_rank(Email.body, query).desc())
        .limit(candidate_limit)
    )


def build_lexical_attachment_stmt(query: str, owner_filters, candidate_limit: int):
    """FTS arm over attachment content, mapped back to the parent email."""
    return (
        select(Attachment.email_id.label("id"), Attachment.content.label("content"))
        .join(Email, Attachment.email_id == Email.id)
        .where(*owner_filters, _fts_match(Attachment.content, query))
        .order_by(_fts_rank(Attachment.content, query).desc())
        .limit(candidate_limit)
    )


def build_vector_email_stmt(query_embedding, owner_filters, candidate_limit: int):
    """ANN arm over email embeddings: pure distance ORDER BY so HNSW applies."""
    return (
        select(Email.id, Email.body.label("content"))
        .where(*owner_filters)
        .order_by(Email.embedding.cosine_distance(query_embedding))
        .limit(candidate_limit)
    )


def build_vector_attachment_stmt(query_embedding, owner_filters, candidate_limit: int):
    return (
        select(Attachment.email_id.label("id"), Attachment.content.label("content"))
        .join(Email, Attachment.email_id == Email.id)
        .where(*owner_filters)
        .order_by(Attachment.embedding.cosine_distance(query_embedding))
        .limit(candidate_limit)
    )


def build_candidate_statements(
    query: str, query_embedding, owner_filters, candidate_limit: int
):
    """Index-eligible candidate arms, strongest evidence first.

    Lexical arms only run with a query string; vector arms only when an
    embedding is available (the full-text fallback path keeps working when
    the embedding provider errors).
    """
    statements = [
        build_lexical_email_stmt(query, owner_filters, candidate_limit),
        build_lexical_attachment_stmt(query, owner_filters, candidate_limit),
    ]
    if query_embedding is not None:
        statements.append(
            build_vector_email_stmt(query_embedding, owner_filters, candidate_limit)
        )
        statements.append(
            build_vector_attachment_stmt(
                query_embedding, owner_filters, candidate_limit
            )
        )
    return statements


def fuse_candidates(arm_rows: list[list]) -> tuple[dict[int, float], dict[int, str]]:
    """Reciprocal-rank fusion across candidate arms.

    Returns fused scores and a representative content snippet source per email
    id (first arm that surfaced the id wins, i.e. strongest evidence).
    """
    scores: dict[int, float] = {}
    contents: dict[int, str] = {}
    for rows in arm_rows:
        for rank, row in enumerate(rows):
            email_id = row.id
            scores[email_id] = scores.get(email_id, 0.0) + 1.0 / (RRF_K + rank + 1)
            if email_id not in contents:
                contents[email_id] = row.content or ""
    return scores, contents


def build_metadata_stmt(email_ids: list[int], owner_filters, reply_counts):
    """Metadata + reply counts for the fused candidates only (bounded set)."""
    return (
        select(
            Email.id,
            Email.message_id.label("source_message_id"),
            Email.subject,
            Email.sender,
            Email.date,
            thread_group_key().label("thread_id"),
            reply_counts.c.reply_count,
        )
        .select_from(Email)
        .join(reply_counts, reply_counts.c.thread_key == thread_group_key())
        .where(*owner_filters, Email.id.in_(email_ids))
    )


def build_search_results(
    scores: dict[int, float],
    contents: dict[int, str],
    metadata_rows,
    limit: int,
) -> list[SearchResultItem]:
    metadata = {row.id: row for row in metadata_rows}
    ranked_ids = sorted(scores, key=lambda email_id: scores[email_id], reverse=True)

    results: list[SearchResultItem] = []
    for email_id in ranked_ids:
        row = metadata.get(email_id)
        if row is None:
            continue
        snippet_source = contents.get(email_id, "")
        snippet = (
            snippet_source[:200] + "..."
            if len(snippet_source) > 200
            else snippet_source
        )
        results.append(
            SearchResultItem(
                id=email_id,
                source_message_id=row.source_message_id,
                subject=row.subject,
                sender=row.sender,
                date=row.date,
                snippet=snippet,
                thread_id=row.thread_id,
                reply_count=row.reply_count or 1,
                score=scores[email_id],
            )
        )
        if len(results) >= limit:
            break
    return results


@router.post("/search", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    user_id: str | None = None,
    config_db: AsyncSession = Depends(get_db),
    search_db: AsyncSession = Depends(get_readonly_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    if user_id and user_id != auth_context.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    target_user_id = user_id or auth_context.user_id

    if not request.query.strip():
        return SearchResponse(results=[])

    try:
        runtime_provider = await resolve_runtime_llm_provider(
            config_db,
            user_id=target_user_id,
            organization_id=auth_context.organization_id,
        )
        if runtime_provider is None:
            raise HTTPException(status_code=400, detail="OpenAI API key not configured")

        query_embedding = None
        try:
            embeddings = await generate_embeddings(
                [request.query],
                runtime_provider.api_key,
                base_url=runtime_provider.base_url,
                model=runtime_provider.embedding_model,
            )
            query_embedding = (
                fit_embedding_vector(embeddings[0], SEARCH_VECTOR_DIMENSIONS)
                if embeddings
                else None
            )
        except EmbeddingGenerationError:
            logger.info("Search embedding unavailable; using full-text search only")

        owner_filters = Email.owner_filters(
            target_user_id, auth_context.organization_id
        )
        candidate_limit = request.limit * 2

        arm_rows = []
        for statement in build_candidate_statements(
            request.query, query_embedding, owner_filters, candidate_limit
        ):
            arm_result = await search_db.execute(statement)
            arm_rows.append(arm_result.all())

        scores, contents = fuse_candidates(arm_rows)
        if not scores:
            return SearchResponse(results=[])

        reply_counts = build_reply_counts_subquery(
            target_user_id, auth_context.organization_id
        )
        metadata_result = await search_db.execute(
            build_metadata_stmt(list(scores), owner_filters, reply_counts)
        )

        search_results = build_search_results(
            scores, contents, metadata_result.all(), request.limit
        )

        return SearchResponse(results=search_results)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Search failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed") from e
