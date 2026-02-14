import logging
from typing import List
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class CPVClassifier:
    """
    Uses LLM (DeepSeek) to map Charity 'Programs & Services' text 
    to a list of relevant CPV (Common Procurement Vocabulary) codes.
    """
    
    SYSTEM_PROMPT = """
    You are an expert in Public Procurement. Your task is to map a Charity's service description
    to the most relevant CPV (Common Procurement Vocabulary) Codes.
    
    Return ONLY a JSON array of strings (CPV Codes). 
    Focus on high-level codes (first 3-5 digits) that capture the core service.
    
    Example Input: "We provide housing support for homeless youth."
    Example Output: ["85311000-2", "98000000-3", "85320000-8"]
    """

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek/deepseek-chat" 

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def predict_cpv_codes(self, service_description: str) -> List[str]:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Service Description:\n{service_description}"}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            content = response.choices[0].message.content.strip()
            # Basic cleaning to ensure JSON array
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "")
            
            import json
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Failed to predict CPV codes: {e}")
            return []
