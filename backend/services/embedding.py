import openai
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from core.config import settings
from services.llm_provider_urls import build_llm_provider_http_client
from services.exceptions import EmbeddingGenerationError
from services.circuit_breaker import provider_circuit_breaker
from services.retry import retry_transient

STORAGE_EMBEDDING_DIMENSION = 1536
# Provider-safe token ceiling for the smallest supported local embedding runtime.
EMBEDDING_INPUT_TOKEN_LIMIT = 256
# Retain the old name for importers that only need the conservative ceiling.
EMBEDDING_INPUT_CHUNK_SIZE = EMBEDDING_INPUT_TOKEN_LIMIT


def chunk_text(
    text: str, chunk_size: int = 1000, chunk_overlap: int = 200
) -> list[str]:
    actual_overlap = min(chunk_overlap, chunk_size // 2)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=actual_overlap,
        length_function=len,
    )
    return splitter.split_text(text)


def fit_embedding_vector(
    embedding: list[float],
    target_dimension: int = STORAGE_EMBEDDING_DIMENSION,
) -> list[float]:
    if target_dimension <= 0:
        raise ValueError("target_dimension must be positive")

    if len(embedding) == target_dimension:
        return list(embedding)
    if len(embedding) < target_dimension:
        return [*embedding, *([0.0] * (target_dimension - len(embedding)))]
    return embedding[:target_dimension]


def _embedding_encoding(model: str | None):
    """Return the selected model tokenizer, with a deterministic local fallback."""
    selected_model = model or settings.OPENAI_EMBEDDING_MODEL
    try:
        return tiktoken.encoding_for_model(selected_model)
    except (KeyError, ValueError):
        return tiktoken.get_encoding("cl100k_base")


def split_embedding_inputs(
    texts: list[str],
    model: str | None = None,
) -> tuple[list[str], list[tuple[int, int]], list[int]]:
    """Split inputs by tokenizer tokens without corrupting UTF-8 boundaries."""
    encoding = _embedding_encoding(model)
    flattened: list[str] = []
    ranges: list[tuple[int, int]] = []
    token_weights: list[int] = []
    for text in texts:
        tokens = encoding.encode(text, disallowed_special=())
        if not tokens:
            chunks = [text]
            weights = [0]
        else:
            chunks = []
            weights = []
            _, offsets = encoding.decode_with_offsets(tokens)
            start = 0
            while start < len(tokens):
                end = min(start + EMBEDDING_INPUT_TOKEN_LIMIT, len(tokens))
                if end < len(tokens):
                    while end > start and offsets[end] == offsets[end - 1]:
                        end -= 1
                    if end == start:
                        end = min(start + EMBEDDING_INPUT_TOKEN_LIMIT, len(tokens))
                        while end < len(tokens) and offsets[end] == offsets[start]:
                            end += 1
                start_character = offsets[start]
                end_character = len(text) if end == len(tokens) else offsets[end]
                chunks.append(text[start_character:end_character])
                weights.append(end - start)
                start = end
        start = len(flattened)
        flattened.extend(chunks)
        token_weights.extend(weights)
        ranges.append((start, len(flattened)))
    return flattened, ranges, token_weights



def pool_embedding_chunks(
    embeddings: list[list[float]],
    ranges: list[tuple[int, int]],
    token_weights: list[int] | None = None,
) -> list[list[float]]:
    """Pool chunk vectors, weighting each chunk by its tokenizer token count."""
    pooled: list[list[float]] = []
    for start, end in ranges:
        chunks = embeddings[start:end]
        if not chunks:
            pooled.append([])
            continue
        weights = (
            token_weights[start:end]
            if token_weights is not None
            else [1] * len(chunks)
        )
        total_weight = sum(weights) or len(chunks)
        width = max(len(chunk) for chunk in chunks)
        pooled.append(
            [
                sum(
                    (
                        chunk[index] if index < len(chunk) else 0.0
                    )
                    * weights[chunk_index]
                    for chunk_index, chunk in enumerate(chunks)
                )
                / total_weight
                for index in range(width)
            ]
        )
    return pooled



async def generate_embeddings(
    texts: list[str],
    openai_api_key: str,
    base_url: str | None = None,
    model: str | None = None,
) -> list[list[float]]:
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    selected_model = model or settings.OPENAI_EMBEDDING_MODEL
    request_texts, input_ranges, token_weights = split_embedding_inputs(
        texts, selected_model
    )

    # Instantiate client locally to avoid global state race conditions across tenants
    configured_base_url = base_url
    if configured_base_url is None:
        configured_base_url = (
            settings.OPENAI_EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
        )
    validated_base_url, http_client = await build_llm_provider_http_client(
        configured_base_url
    )
    client = AsyncOpenAI(
        api_key=openai_api_key,
        base_url=validated_base_url,
        http_client=http_client,
    )

    try:
        response = await provider_circuit_breaker.call(
            validated_base_url or "openai-default",
            lambda: retry_transient(
                lambda: client.embeddings.create(
                    model=selected_model,
                    input=request_texts,
                ),
                operation_name="embedding generation",
            ),
        )
        return pool_embedding_chunks(
            [data.embedding for data in response.data],
            input_ranges,
            token_weights,
        )
    except openai.OpenAIError as e:
        raise EmbeddingGenerationError(f"Failed to generate embeddings: {str(e)}")
    finally:
        await client.close()
