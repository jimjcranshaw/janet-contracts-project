import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure app module is found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock pgvector before importing app modules
try:
    import pgvector
except ImportError:
    import sqlalchemy
    sys.modules["pgvector"] = MagicMock()
    sys.modules["pgvector.sqlalchemy"] = MagicMock()
    sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.NullType()

from app.services.matching.cpv_classifier import CPVClassifier
from app.services.matching.translator import ProviderTranslator

@pytest.mark.asyncio
async def test_cpv_classifier_predict():
    # 1. Mock OpenAI
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='["85311000-2", "98000000-3"]'))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    # 2. Init Classifier with mock
    classifier = CPVClassifier(api_key="fake")
    classifier.client = mock_client
    
    # 3. Predict & Assert
    result = await classifier.predict_cpv_codes("Housing support service")
    assert result == ["85311000-2", "98000000-3"]
    assert mock_client.chat.completions.create.called

@pytest.mark.asyncio
async def test_translator_translate():
    # 1. Mock OpenAI
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Aspirational summary."))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    # 2. Init Translator
    translator = ProviderTranslator(api_key="fake")
    translator.client = mock_client
    
    # 3. Translate & Assert
    result = await translator.translate_notice("Tech Title", "Tech Desc")
    assert result == "Aspirational summary."
    assert mock_client.chat.completions.create.called
