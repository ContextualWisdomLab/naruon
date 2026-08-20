import pytest
import tiktoken
import openai
from unittest.mock import patch, AsyncMock


from services.embedding import (
    EMBEDDING_INPUT_TOKEN_LIMIT,
    STORAGE_EMBEDDING_DIMENSION,
    chunk_text,
    fit_embedding_vector,
    generate_embeddings,
    pool_embedding_chunks,
    split_embedding_inputs,
)
from services.exceptions import EmbeddingGenerationError

class _ProviderResponse:
    def __init__(self, payload, *, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def test_split_embedding_inputs_preserves_unicode_at_token_boundaries():
    """Keep source text intact when a token boundary bisects UTF-8 bytes."""
    source = "é" * 237 + "😀" * 10

    flattened, ranges, weights = split_embedding_inputs(
        [source],
        model="test-model",
    )

    encoding = tiktoken.get_encoding("cl100k_base")
    assert ranges == [(0, len(flattened))]
    assert "".join(flattened) == source
    assert "\ufffd" not in "".join(flattened)
    assert all(
        len(encoding.encode(text, disallowed_special=())) <= EMBEDDING_INPUT_TOKEN_LIMIT
        for text in flattened
    )
    assert sum(weights) == len(encoding.encode(source, disallowed_special=()))

def test_chunk_text():
    text = "This is a long test string. " * 100
    chunks = chunk_text(text, chunk_size=50)
    assert len(chunks) > 1
    assert len(chunks[0]) <= 50


def test_fit_embedding_vector_pads_embeddinggemma_dimension_to_storage_vector():
    fitted = fit_embedding_vector([0.25] * 768)

    assert len(fitted) == STORAGE_EMBEDDING_DIMENSION
    assert fitted[:768] == [0.25] * 768
    assert fitted[768:] == [0.0] * (STORAGE_EMBEDDING_DIMENSION - 768)


def test_fit_embedding_vector_truncates_larger_provider_dimension():
    fitted = fit_embedding_vector([0.5] * 3072)

    assert len(fitted) == STORAGE_EMBEDDING_DIMENSION
    assert fitted == [0.5] * STORAGE_EMBEDDING_DIMENSION


def test_split_embedding_inputs_respects_token_limit_and_returns_weights():
    flattened, ranges, weights = split_embedding_inputs(
        ["token " * 600],
        model="test-model",
    )

    encoding = tiktoken.get_encoding("cl100k_base")
    assert ranges == [(0, len(flattened))]
    assert len(flattened) == len(weights)
    assert all(
        0 < weight <= EMBEDDING_INPUT_TOKEN_LIMIT
        and len(encoding.encode(text, disallowed_special=())) == weight
        for text, weight in zip(flattened, weights)
    )


def test_pool_embedding_chunks_weights_by_token_count():
    assert pool_embedding_chunks(
        [[1.0], [3.0]],
        [(0, 2)],
        [1, 3],
    ) == [[2.5]]


@pytest.mark.asyncio
async def test_generate_embeddings_success():
    with patch(
        "services.embedding.AsyncOpenAI"
    ) as mock_async_openai:
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()
        mock_client.embeddings.create = AsyncMock()
        mock_response = AsyncMock()
        mock_data_1 = AsyncMock()
        mock_data_1.embedding = [0.1, 0.2, 0.3]
        mock_data_2 = AsyncMock()
        mock_data_2.embedding = [0.4, 0.5, 0.6]
        mock_response.data = [mock_data_1, mock_data_2]
        mock_client.embeddings.create.return_value = mock_response

        with patch("services.embedding.settings") as mock_settings:
            mock_settings.OPENAI_EMBEDDING_MODEL = "test-model"
            mock_settings.OPENAI_BASE_URL = None
            mock_settings.OPENAI_EMBEDDING_BASE_URL = None

            embeddings = await generate_embeddings(["test1", "test2"], "test-key")
            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2, 0.3]
            assert embeddings[1] == [0.4, 0.5, 0.6]
            mock_client.embeddings.create.assert_awaited_once_with(
                model="test-model", input=["test1", "test2"]
            )
            mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_embeddings_uses_selected_provider_model_and_base_url():
    with patch("services.embedding.AsyncOpenAI") as mock_async_openai, patch(
        "services.embedding.build_llm_provider_http_client",
        new_callable=AsyncMock,
    ) as mock_build_client:
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            side_effect=[
                _ProviderResponse({"tokens": [1]}),
                _ProviderResponse({"content": "test"}),
            ]
        )
        mock_build_client.return_value = ("http://ollama:11434/v1", mock_http_client)
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()
        mock_client.embeddings.create = AsyncMock()
        mock_response = AsyncMock()
        mock_data = AsyncMock()
        mock_data.embedding = [0.1, 0.2, 0.3]
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response

        embeddings = await generate_embeddings(
            ["test"],
            "local-provider",
            base_url="http://ollama:11434/v1",
            model="embeddinggemma",
        )

    assert embeddings == [[0.1, 0.2, 0.3]]
    mock_build_client.assert_awaited_once_with("http://ollama:11434/v1")
    mock_client.embeddings.create.assert_awaited_once_with(
        model="embeddinggemma", input=["test"]
    )
    mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_embeddings_uses_provider_native_tokenizer_for_local_model():
    with patch("services.embedding.AsyncOpenAI") as mock_async_openai, patch(
        "services.embedding.build_llm_provider_http_client",
        new_callable=AsyncMock,
    ) as mock_build_client:
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            side_effect=[
                _ProviderResponse({"tokens": [1, 2, 3]}),
                _ProviderResponse({"content": "test"}),
            ]
        )
        mock_build_client.return_value = ("http://host.docker.internal:8082/v1", mock_http_client)
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()
        mock_response = AsyncMock()
        mock_response.data = [AsyncMock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        embeddings = await generate_embeddings(
            ["test"],
            "local-provider",
            base_url="http://host.docker.internal:8082/v1",
            model="embeddinggemma",
        )

    assert embeddings == [[0.1, 0.2, 0.3]]
    assert mock_http_client.post.await_count == 2
    assert mock_http_client.post.await_args_list[0].args[0].endswith("/tokenize")
    assert mock_http_client.post.await_args_list[1].args[0].endswith("/detokenize")

@pytest.mark.asyncio
async def test_generate_embeddings_falls_back_for_remote_unknown_model_without_native_tokenizer():
    with patch("services.embedding.AsyncOpenAI") as mock_async_openai, patch(
        "services.embedding.build_llm_provider_http_client",
        new_callable=AsyncMock,
    ) as mock_build_client:
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            return_value=_ProviderResponse({}, status_code=404)
        )
        mock_build_client.return_value = (
            "https://remote.example/v1", mock_http_client
        )
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()
        mock_client.embeddings.create = AsyncMock(
            return_value=AsyncMock(data=[AsyncMock(embedding=[0.1, 0.2, 0.3])])
        )

        embeddings = await generate_embeddings(
            ["test"],
            "remote-key",
            base_url="https://remote.example/v1",
            model="remote-custom-model",
        )

    assert embeddings == [[0.1, 0.2, 0.3]]
    mock_http_client.post.assert_awaited_once()
    mock_client.embeddings.create.assert_awaited_once_with(
        model="remote-custom-model", input=["test"]
    )
    mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_embeddings_prefers_embedding_base_url_when_no_explicit_url():
    with patch(
        "services.embedding.AsyncOpenAI"
    ) as mock_async_openai, patch(
        "services.embedding.build_llm_provider_http_client",
        new_callable=AsyncMock,
    ) as mock_build_client:
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            side_effect=[
                _ProviderResponse({"tokens": [1]}),
                _ProviderResponse({"content": "test"}),
            ]
        )
        mock_build_client.return_value = (
            "http://host.docker.internal:8082/v1", mock_http_client
        )
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=AsyncMock(data=[]))

        with patch("services.embedding.settings") as mock_settings:
            mock_settings.OPENAI_EMBEDDING_BASE_URL = (
                "http://host.docker.internal:8082/v1"
            )
            mock_settings.OPENAI_BASE_URL = "http://host.docker.internal:8080/v1"
            mock_settings.OPENAI_EMBEDDING_MODEL = "embeddinggemma"
            with pytest.raises(ValueError, match="unexpected vector count"):
                await generate_embeddings(["test"], "local-provider")

    mock_build_client.assert_awaited_once_with("http://host.docker.internal:8082/v1")


@pytest.mark.asyncio
async def test_generate_embeddings_closes_http_client_when_openai_constructor_fails():
    mock_http_client = AsyncMock()
    with patch(
        "services.embedding.build_llm_provider_http_client",
        new_callable=AsyncMock,
        return_value=(None, mock_http_client),
    ), patch(
        "services.embedding.AsyncOpenAI",
        side_effect=RuntimeError("client construction failed"),
    ):
        with pytest.raises(RuntimeError, match="client construction failed"):
            await generate_embeddings(["test"], "provider-key")

    mock_http_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_embeddings_requests_storage_dimensions_for_openai_v3():
    with patch(
        "services.embedding.AsyncOpenAI"
    ) as mock_async_openai, patch(
        "services.embedding.build_llm_provider_http_client",
        new_callable=AsyncMock,
    ) as mock_build_client:
        mock_build_client.return_value = ("https://api.openai.com/v1", AsyncMock())
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()
        mock_client.embeddings.create = AsyncMock()
        mock_response = AsyncMock()
        mock_data = AsyncMock()
        mock_data.embedding = [0.1, 0.2]
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response

        await generate_embeddings(
            ["test"],
            "provider-key",
            base_url="https://api.openai.com/v1",
            model="text-embedding-3-large",
        )

    mock_client.embeddings.create.assert_awaited_once_with(
        model="text-embedding-3-large",
        input=["test"],
        dimensions=STORAGE_EMBEDDING_DIMENSION,
    )


@pytest.mark.asyncio
async def test_generate_embeddings_api_error():
    with patch(
        "services.embedding.AsyncOpenAI"
    ) as mock_async_openai:
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()
        mock_client.embeddings.create = AsyncMock(side_effect=openai.OpenAIError("API error"))

        with patch("services.embedding.settings") as mock_settings:
            mock_settings.OPENAI_EMBEDDING_MODEL = "test-model"
            mock_settings.OPENAI_BASE_URL = None
            mock_settings.OPENAI_EMBEDDING_BASE_URL = None
            
            with pytest.raises(EmbeddingGenerationError, match="Failed to generate embeddings: API error"):

                await generate_embeddings(["test"], "test-key")
            mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_embeddings_pools_token_safe_chunks():
    with patch("services.embedding.AsyncOpenAI") as mock_async_openai:
        mock_client = mock_async_openai.return_value
        mock_client.close = AsyncMock()

        async def create_embeddings(*, model, input):
            assert model == "test-model"
            assert input
            encoding = tiktoken.get_encoding("cl100k_base")
            assert all(
                0 < len(encoding.encode(item, disallowed_special=()))
                <= EMBEDDING_INPUT_TOKEN_LIMIT
                for item in input
            )
            response = AsyncMock()
            response.data = [
                AsyncMock(embedding=[float(index + 1)])
                for index, _item in enumerate(input)
            ]
            return response

        mock_client.embeddings.create = AsyncMock(side_effect=create_embeddings)

        with patch("services.embedding.settings") as mock_settings:
            mock_settings.OPENAI_EMBEDDING_MODEL = "test-model"
            mock_settings.OPENAI_BASE_URL = None
            mock_settings.OPENAI_EMBEDDING_BASE_URL = None

            embeddings = await generate_embeddings(["token " * 600], "test-key")

    assert len(embeddings) == 1
    assert embeddings[0][0] >= 1.0
    mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_embeddings_missing_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        await generate_embeddings(["test"], "")
