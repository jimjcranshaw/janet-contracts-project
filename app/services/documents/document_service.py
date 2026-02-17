import logging
import requests
import io
from typing import Optional
from pdfminer.high_level import extract_text
from pdfminer.pdftypes import PDFException

logger = logging.getLogger(__name__)

class DocumentService:
    """
    Handles fetching and parsing tender documents (PRD 07).
    Supported formats: PDF (primary), Text.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def fetch_and_extract_text(self, url: str) -> Optional[str]:
        """
        Downloads a document and extracts text content.
        """
        try:
            logger.info(f"Fetching document from {url}")
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'pdf' in content_type or url.lower().endswith('.pdf'):
                return self._extract_from_pdf(response.content)
            else:
                # Fallback to plain text / HTML strip
                return response.text
                
        except Exception as e:
            logger.error(f"Failed to fetch/extract document from {url}: {e}")
            return None

    def _extract_from_pdf(self, pdf_content: bytes) -> str:
        """
        Extracts text from PDF bytes.
        """
        try:
            with io.BytesIO(pdf_content) as fh:
                text = extract_text(fh)
                return text.strip()
        except PDFException as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error during PDF extraction: {e}")
            return ""

    def summarize_text(self, text: str, max_chars: int = 10000) -> str:
        """
        Truncates or cleans text for LLM consumption.
        """
        if not text:
            return ""
        # Basic cleaning: remove extra whitespace
        cleaned = " ".join(text.split())
        return cleaned[:max_chars]
