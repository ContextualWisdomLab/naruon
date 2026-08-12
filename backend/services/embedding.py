import openai
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from core.config import settings
from services.llm_provider_urls import build_llm_provider_http_client
from services.exceptions import EmbeddingGenerationError
from services.circuit_breaker import provider_circuit_breaker
from services.retry import retry_transient

STORAGE_EMBEDDING_DIMENSION = 1536
# Keep each request below the smallest local embedding context observed in the
# supported llama.cpp/EmbeddingGemma runtime. Longer source items are pooled
# back to one vector per caller input.
EMBEDDING_INPUT_CHUNK_SIZE = 256


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


def _split_embedding_inputs(
    texts: list[str],
) -> tuple[list[str], list[tuple[int, int]]]:
    flattened: list[str] = []
    ranges: list[tuple[int, int]] = []
    for text in texts:
        chunks = chunk_text(
            text,
            chunk_size=EMBEDDING_INPUT_CHUNK_SIZE,
            chunk_overlap=0,
        ) or [text]
        start = len(flattened)
        flattened.extend(chunks)
        ranges.append((start, len(flattened)))
    return flattened, ranges


def _pool_embedding_chunks(
    embeddings: list[list[float]], ranges: list[tuple[int, int]]
) -> list[list[float]]:
    pooled: list[list[float]] = []
    for start, end in ranges:
        chunks = embeddings[start:end]
        if not chunks:
            pooled.append([])
            continue
        width = max(len(chunk) for chunk in chunks)
        pooled.append(
            [
                sum(
                    chunk[index] if index < len(chunk) else 0.0
                    for chunk in chunks
                )
                / len(chunks)
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

    request_texts, input_ranges = _split_embedding_inputs(texts)

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
                    model=model or settings.OPENAI_EMBEDDING_MODEL,
                    input=request_texts,
                ),
                operation_name="embedding generation",
            ),
        )
        return _pool_embedding_chunks(
            [data.embedding for data in response.data], input_ranges
        )
    except openai.OpenAIError as e:
        raise EmbeddingGenerationError(f"Failed to generate embeddings: {str(e)}")
    finally:
        await client.close()
