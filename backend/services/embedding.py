import openai
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from urllib.parse import urlsplit, urlunsplit
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


def _requires_provider_tokenizer(model: str, base_url: str | None) -> bool:
    """Require a native tokenizer for an unknown model on a configured endpoint."""
    if not base_url:
        return False
    try:
        tiktoken.encoding_for_model(model)
    except (KeyError, ValueError):
        return True
    return False


def _provider_endpoint(base_url: str, resource: str) -> str:
    """Build a root-level llama.cpp tokenizer endpoint from an OpenAI base URL."""
    parsed = urlsplit(base_url)
    base_path = parsed.path.rstrip("/")
    if base_path.endswith("/v1"):
        base_path = base_path[:-3]
    return urlunsplit(
        (parsed.scheme, parsed.netloc, f"{base_path}/{resource}", "", "")
    )


class _ProviderTokenizerUnavailable(ValueError):
    """Signal that a provider does not expose the optional native tokenizer."""


async def _provider_json(
    http_client,
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
) -> dict:
    """POST one native tokenizer request and validate its JSON object response."""
    response = await http_client.post(url, json=payload, headers=headers)
    if response.status_code == 404:
        raise _ProviderTokenizerUnavailable(
            "embedding provider does not expose native tokenizer endpoints"
        )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("embedding provider returned a non-object tokenizer response")
    return body


async def _split_embedding_inputs_with_provider_tokenizer(
    texts: list[str],
    model: str,
    base_url: str,
    http_client,
    api_key: str,
) -> tuple[list[str], list[tuple[int, int]], list[int]]:
    """Split unknown local-model inputs using the provider tokenizer itself."""
    tokenize_url = _provider_endpoint(base_url, "tokenize")
    detokenize_url = _provider_endpoint(base_url, "detokenize")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    flattened: list[str] = []
    ranges: list[tuple[int, int]] = []
    token_weights: list[int] = []
    for text in texts:
        if not text:
            start = len(flattened)
            flattened.append(text)
            token_weights.append(0)
            ranges.append((start, len(flattened)))
            continue
        token_response = await _provider_json(
            http_client,
            tokenize_url,
            {
                "content": text,
                "add_special": False,
                "parse_special": False,
            },
            headers=headers,
        )
        tokens = token_response.get("tokens")
        if not isinstance(tokens, list) or not all(
            isinstance(token, int) and not isinstance(token, bool) for token in tokens
        ):
            raise ValueError("embedding provider returned invalid tokenizer tokens")
        if not tokens:
            start = len(flattened)
            flattened.append(text)
            token_weights.append(0)
            ranges.append((start, len(flattened)))
            continue
        start = len(flattened)
        for token_start in range(0, len(tokens), EMBEDDING_INPUT_TOKEN_LIMIT):
            token_slice = tokens[
                token_start : token_start + EMBEDDING_INPUT_TOKEN_LIMIT
            ]
            detokenized = await _provider_json(
                http_client,
                detokenize_url,
                {"tokens": token_slice},
                headers=headers,
            )
            chunk = detokenized.get("content")
            if not isinstance(chunk, str):
                raise ValueError(
                    "embedding provider returned invalid detokenized content"
                )
            flattened.append(chunk)
            token_weights.append(len(token_slice))
        if "".join(flattened[start:]) != text:
            raise ValueError(
                "embedding provider tokenizer did not preserve source text exactly"
            )
        ranges.append((start, len(flattened)))
    return flattened, ranges, token_weights

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
                    * (weights[chunk_index] / total_weight)
                    for chunk_index, chunk in enumerate(chunks)
                )
                for index in range(width)
            ]
        )
    return pooled

def _supports_native_dimensions(model: str) -> bool:
    """Return whether the selected OpenAI embedding family accepts dimensions."""
    return model.rsplit("/", 1)[-1].startswith("text-embedding-3-")


async def generate_embeddings(
    texts: list[str],
    openai_api_key: str,
    base_url: str | None = None,
    model: str | None = None,
) -> list[list[float]]:
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    selected_model = model or settings.OPENAI_EMBEDDING_MODEL
    configured_base_url = base_url
    if configured_base_url is None:
        configured_base_url = (
            settings.OPENAI_EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
        )

    # Instantiate the pinned client before tokenization so unknown local models
    # use the exact tokenizer loaded by the provider rather than cl100k_base.
    validated_base_url, http_client = await build_llm_provider_http_client(
        configured_base_url
    )
    try:
        if _requires_provider_tokenizer(selected_model, validated_base_url):
            try:
                request_texts, input_ranges, token_weights = (
                    await _split_embedding_inputs_with_provider_tokenizer(
                        texts,
                        selected_model,
                        validated_base_url,
                        http_client,
                        openai_api_key,
                    )
                )
            except _ProviderTokenizerUnavailable:
                request_texts, input_ranges, token_weights = split_embedding_inputs(
                    texts, selected_model
                )
        else:
            request_texts, input_ranges, token_weights = split_embedding_inputs(
                texts, selected_model
            )
    except Exception:
        await http_client.aclose()
        raise

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
                    **(
                        {"dimensions": STORAGE_EMBEDDING_DIMENSION}
                        if _supports_native_dimensions(selected_model)
                        else {}
                    ),
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
