import logging
from typing import List, Dict, Any, Optional
from groq import Groq
from config import settings

logger = logging.getLogger(__name__)

class GroqService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.primary_model = settings.GROQ_MODEL
        self.fallback_model = settings.GROQ_FALLBACK_MODEL
        self.client = Groq(api_key=self.api_key) if self.api_key else None
        self._active_model = None

    def get_completion(self, messages: List[Dict[str, str]], temperature: float = 0.4, max_tokens: int = 350) -> str:
        if not self.client:
            raise ValueError("Groq API client is not initialized. Please check GROQ_API_KEY.")

        # Determine model order
        models_to_try = []
        if self._active_model:
            models_to_try.append(self._active_model)
        if self.primary_model not in models_to_try:
            models_to_try.append(self.primary_model)
        if self.fallback_model not in models_to_try:
            models_to_try.append(self.fallback_model)
        # Additional safety fallbacks available on Groq
        for alt in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
            if alt not in models_to_try:
                models_to_try.append(alt)

        last_error = None
        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self._active_model = model
                content = response.choices[0].message.content or ""
                return content.strip()
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Groq completion failed with model {model}: {err_str}")
                last_error = e
                # If error is model not found or invalid request, try next model
                continue

        raise RuntimeError(f"All Groq models failed. Last error: {last_error}")

groq_service = GroqService()
