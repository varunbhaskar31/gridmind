"""Resilient Google Gemini LLM client wrapper with mock fallback and schema validation.

Design Principles:
- The system must run without an LLM (MOCK_LLM=true).
- Any LLM failure (quota, timeout, invalid key, rate limit) automatically falls back to deterministic mock logic.
- Low temperature (0.2) for reliable decision-making.
- Automatic single retry on malformed JSON before fallback.
- Tracks API call counts and fallback occurrences.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Wrapper around Gemini API with fallback to deterministic mock logic."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        self.force_mock = os.getenv("MOCK_LLM", "false").lower() in ["true", "1", "yes"]

        self.call_count: int = 0
        self.fallback_count: int = 0

        self._client = None
        if not self.force_mock and self.api_key and self.api_key != "your_api_key_here":
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI client with model %s", self.model_name)
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI client: %s. Defaulting to mock mode.", e)
                self._client = None
        else:
            if self.force_mock:
                logger.info("MOCK_LLM=true enabled. Operating in deterministic offline mock mode.")
            else:
                logger.info("No valid GEMINI_API_KEY found. Operating in deterministic offline mock mode.")

    @property
    def is_mock(self) -> bool:
        """Whether client is operating in mock mode."""
        return self._client is None

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: str = "",
        fallback_fn: Optional[Any] = None,
        fallback_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[T, bool]:
        """Generate structured Pydantic object from prompt with fallback on error.

        Args:
            prompt: User/task instruction string.
            schema: Pydantic model class for expected output.
            system_instruction: System prompt framing agent persona and rules.
            fallback_fn: Deterministic callable to invoke if LLM fails or mock is active.
            fallback_kwargs: Keyword arguments for fallback callable.

        Returns:
            Tuple of (PydanticModelInstance, used_mock_fallback: bool).
        """
        self.call_count += 1
        kwargs = fallback_kwargs or {}

        if self.is_mock or fallback_fn is None:
            if fallback_fn:
                self.fallback_count += 1
                return fallback_fn(**kwargs), True

        # Attempt call to live Gemini API
        try:
            from google.genai import types

            json_schema_prompt = (
                f"{prompt}\n\nIMPORTANT: Output ONLY valid JSON adhering strictly to this schema:\n"
                f"{json.dumps(schema.model_json_schema())}\n"
            )

            config = types.GenerateContentConfig(
                temperature=0.2,
                system_instruction=system_instruction or None,
                response_mime_type="application/json",
            )

            resp = self._client.models.generate_content(
                model=self.model_name,
                contents=json_schema_prompt,
                config=config,
            )

            raw_text = resp.text.strip()
            # Clean markdown codeblocks if present
            cleaned_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()

            try:
                parsed = schema.model_validate_json(cleaned_text)
                return parsed, False
            except Exception as val_err:
                logger.warning("JSON schema validation failed: %s. Attempting single retry with error feedback...", val_err)

                # Retry once with error feedback appended
                retry_prompt = (
                    f"{json_schema_prompt}\n\nPREVIOUS ERROR: Your previous JSON output was invalid:\n{val_err}\n"
                    f"Please correct the error and output valid JSON only."
                )
                retry_resp = self._client.models.generate_content(
                    model=self.model_name,
                    contents=retry_prompt,
                    config=config,
                )
                retry_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", retry_resp.text.strip(), flags=re.MULTILINE).strip()
                parsed = schema.model_validate_json(retry_text)
                return parsed, False

        except Exception as e:
            logger.warning("Gemini LLM call failed: %s. Falling back to deterministic mock logic.", e)
            self.fallback_count += 1
            if fallback_fn:
                return fallback_fn(**kwargs), True
            raise
