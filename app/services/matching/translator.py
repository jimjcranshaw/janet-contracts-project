import logging
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class ProviderTranslator:
    """
    Rewrites technical procurement notices into aspirational 'Provider Summaries'.
    This bridges the vocabulary gap between Bureaucratic Buyers and Mission-Driven Charities.
    """
    
    SYSTEM_PROMPT = """
    You are a bridge between Government Procurement and Examples of Work for Charities.
    
    Rewrite the provided technically-worded Procurement Notice into a 
    "Service Delivery Summary" that focuses on the human impact and core activities.
    
    Target Audience: A Charity CEO or Service Manager.
    Tone: Aspirational but clear.
    
    Example Input: "Provision of Lot 2 Level 3 Employability Support Services per Framework Agreement..."
    Example Output: "Delivering mentorship and training programs to help unemployed individuals gain skills and find sustainable work."
    """

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek/deepseek-chat"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def translate_notice(self, title: str, description: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Title: {title}\nDescription: {description}"}
                ],
                temperature=0.3,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to translate notice: {e}")
            return f"{title}: {description}"[:500] # Fallback
