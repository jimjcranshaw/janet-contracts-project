import logging
from typing import List, Optional
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from app.database import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. Embedding generation will fail.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        """
        if not text:
            return []
        
        # Replace newlines which can negatively affect performance
        text = text.replace("\n", " ")
        
        response = self.client.embeddings.create(input=[text], model=self.model)
        return response.data[0].embedding

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        """
        if not texts:
            return []
        
        # Clean texts
        cleaned_texts = [t.replace("\n", " ") if t else "" for t in texts]
        
        # If any text is empty, OpenAI might error or return partial results depending on the API version.
        # It's safer to filter or handle empty strings specifically if needed, but usually we expect descriptions.
        
        response = self.client.embeddings.create(input=cleaned_texts, model=self.model)
        return [item.embedding for item in response.data]

if __name__ == "__main__":
    # Quick test
    service = EmbeddingService()
    try:
        vec = service.get_embedding("Test embedding generation")
        print(f"Embedding generated: length {len(vec)}")
    except Exception as e:
        print(f"Error: {e}")
