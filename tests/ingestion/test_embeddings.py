import pytest
from unittest.mock import MagicMock, patch
from app.services.ingestion.embeddings import EmbeddingService

@pytest.fixture
def mock_openai():
    with patch('app.services.ingestion.embeddings.OpenAI') as mock:
        yield mock

def test_get_embedding_success(mock_openai):
    # Setup mock response
    mock_client = mock_openai.return_value
    mock_response = MagicMock()
    mock_data = MagicMock()
    mock_data.embedding = [0.1, 0.2, 0.3]
    mock_response.data = [mock_data]
    mock_client.embeddings.create.return_value = mock_response

    service = EmbeddingService(api_key="test-key")
    embedding = service.get_embedding("hello world")

    assert embedding == [0.1, 0.2, 0.3]
    mock_client.embeddings.create.assert_called_once_with(
        input=["hello world"],
        model="text-embedding-3-small"
    )

def test_get_embeddings_batch_success(mock_openai):
    # Setup mock response
    mock_client = mock_openai.return_value
    mock_response = MagicMock()
    mock_data1 = MagicMock()
    mock_data1.embedding = [0.1, 0.1]
    mock_data2 = MagicMock()
    mock_data2.embedding = [0.2, 0.2]
    mock_response.data = [mock_data1, mock_data2]
    mock_client.embeddings.create.return_value = mock_response

    service = EmbeddingService(api_key="test-key")
    embeddings = service.get_embeddings_batch(["text1", "text2"])

    assert len(embeddings) == 2
    assert embeddings[0] == [0.1, 0.1]
    assert embeddings[1] == [0.2, 0.2]
    mock_client.embeddings.create.assert_called_once_with(
        input=["text1", "text2"],
        model="text-embedding-3-small"
    )

def test_get_embedding_empty_input(mock_openai):
    service = EmbeddingService(api_key="test-key")
    assert service.get_embedding("") == []
    assert service.get_embeddings_batch([]) == []
