"""
AI Service - Arsenal Module
OpenRouter client with retry logic and dual API support
Copy-paste ready: Just provide config
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from openai import AsyncOpenAI
import logging

from lib.query_errors import (
    AuthenticationError,
    InvalidModelOutputError,
    ModelNotFoundError,
    ProviderTransientError,
    QueryTimeoutError,
    QuotaError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StructuredOutputSchema:
    """JSON-schema response format for providers that support structured outputs."""

    name: str
    schema: dict[str, object]
    strict: bool = True

    def as_response_format(self) -> dict[str, object]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.name,
                "schema": self.schema,
                "strict": self.strict,
            },
        }


class AIService:
    """AI Service for OpenRouter API with exponential backoff retry"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        referer: str,
        app_name: str,
        max_retries: int = 5,
        retry_delay: int = 2,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_delay < 0:
            raise ValueError("retry_delay must be >= 0")

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.structured_output_support: Dict[str, bool] = {}

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": referer,
                "X-Title": app_name
            }
        )

    @staticmethod
    def _extract_text_from_parts(parts: Any) -> str:
        """Extract text from structured content parts returned by some providers."""
        if not isinstance(parts, list):
            return ""

        extracted: List[str] = []
        for part in parts:
            if isinstance(part, str):
                text = part.strip()
                if text:
                    extracted.append(text)
                continue

            if isinstance(part, dict):
                text_value = part.get("text")
                if isinstance(text_value, str):
                    text = text_value.strip()
                    if text:
                        extracted.append(text)
                continue

            text_attr = getattr(part, "text", None)
            if isinstance(text_attr, str):
                text = text_attr.strip()
                if text:
                    extracted.append(text)

        return "\n".join(extracted)

    def _extract_response_text(self, response: Any) -> str:
        """Extract best-effort text across chat/completions provider variants."""
        choices = getattr(response, "choices", None)
        if not choices:
            return ""

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)

        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text = self._extract_text_from_parts(content)
            if text:
                return text

        # Some providers populate refusal text instead of content.
        refusal = getattr(message, "refusal", None)
        if isinstance(refusal, str) and refusal.strip():
            return refusal.strip()

        # Some providers expose reasoning separately.
        reasoning = getattr(message, "reasoning", None)
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()
        if isinstance(reasoning, list):
            text = self._extract_text_from_parts(reasoning)
            if text:
                return text

        # Defensive fallback for non-chat shape.
        choice_text = getattr(first_choice, "text", None)
        if isinstance(choice_text, str) and choice_text.strip():
            return choice_text.strip()

        return ""

    @staticmethod
    def _empty_response_error(response: Any) -> str:
        """Create an actionable error when a provider returns no usable text."""
        choices = getattr(response, "choices", None)
        if not choices:
            return "Model returned no choices"

        finish_reason = getattr(choices[0], "finish_reason", None)
        if finish_reason == "length":
            return "Model hit max_tokens before yielding visible output"
        if finish_reason == "content_filter":
            return "Model response blocked by provider content filter"

        return "Model returned no usable text content"

    @staticmethod
    def _is_structured_output_unsupported(error: Exception) -> bool:
        """Return True when the provider rejects response_format/json_schema."""
        message = str(error).lower()
        mentions_schema = any(
            marker in message
            for marker in ("response_format", "json_schema", "structured output", "structured outputs")
        )
        if not mentions_schema:
            return False
        return any(
            marker in message
            for marker in (
                "unsupported",
                "not support",
                "not available",
                "invalid",
                "unrecognized",
                "unknown parameter",
            )
        )

    async def get_model_response(
        self,
        model_name: str,
        prompt: str,
        system_prompt: str = "",
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
        *,
        response_schema: Optional[StructuredOutputSchema] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """
        Get model response with automatic retry logic

        Args:
            model_name: Model identifier
            prompt: User prompt
            system_prompt: Optional system prompt for ethical priming
            params: Generation parameters
            retry_count: Current retry attempt (internal)

        Returns:
            Tuple of (Model response text, Usage dictionary)
        """
        if params is None:
            params = {}

        try:
            # Build request parameters
            request_params = {
                "model": model_name,
                "temperature": params.get("temperature", 1.0),
                "top_p": params.get("top_p", 1.0),
                "max_tokens": params.get("max_tokens", 1000),
                "frequency_penalty": params.get("frequency_penalty", 0),
                "presence_penalty": params.get("presence_penalty", 0)
            }

            # Only include seed if provided
            if params.get("seed") is not None:
                request_params["seed"] = params["seed"]

            messages: List[Dict[str, str]]
            if system_prompt and system_prompt.strip():
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            else:
                messages = [{"role": "user", "content": prompt}]

            use_structured_output = (
                response_schema is not None
                and self.structured_output_support.get(model_name, True)
            )
            if use_structured_output and response_schema is not None:
                request_params["response_format"] = response_schema.as_response_format()

            try:
                response = await self.client.chat.completions.create(
                    **request_params,
                    messages=messages
                )
            except Exception as api_error:
                if use_structured_output and self._is_structured_output_unsupported(api_error):
                    logger.info(
                        "Structured outputs unsupported for %s; falling back to prompt-only JSON",
                        model_name,
                    )
                    self.structured_output_support[model_name] = False
                    request_params.pop("response_format", None)
                    response = await self.client.chat.completions.create(
                        **request_params,
                        messages=messages,
                    )
                else:
                    if "JSON" in str(api_error):
                        logger.error("JSON parsing error - API may have returned HTML or empty response")
                        logger.error("Model: %s, Retry count: %s", model_name, retry_count)
                    raise
            else:
                if use_structured_output:
                    self.structured_output_support[model_name] = True

            response_text = self._extract_response_text(response)
            if response_text:
                usage = getattr(response, "usage", None)
                usage_dict = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                }
                return response_text, usage_dict

            raise Exception(self._empty_response_error(response))

        except Exception as error:
            return await self._handle_error(
                error,
                model_name,
                prompt,
                system_prompt,
                params,
                retry_count,
                response_schema=response_schema,
            )

    async def _handle_error(
        self,
        error: Exception,
        model_name: str,
        prompt: str,
        system_prompt: str,
        params: Dict[str, Any],
        retry_count: int,
        response_schema: Optional[StructuredOutputSchema] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Handle errors with retry logic"""
        logger.error("Error querying OpenRouter: %s", error)

        # Check for status code in error
        status_code = getattr(error, "status_code", None)
        error_msg = str(error)
        error_msg_lower = error_msg.lower()

        if status_code:
            # Retry on 429 (rate limit) or 5xx (server errors)
            should_retry = (
                (status_code == 429 or status_code >= 500)
                and retry_count < self.max_retries
            )

            if should_retry:
                delay = self.retry_delay * (2 ** retry_count)
                logger.info(
                    "Retrying after %ss (attempt %s/%s)...",
                    delay,
                    retry_count + 1,
                    self.max_retries,
                )
                await asyncio.sleep(delay)
                return await self.get_model_response(
                    model_name,
                    prompt,
                    system_prompt,
                    params,
                    retry_count + 1,
                    response_schema=response_schema,
                )

            # Add context based on status code
            if status_code == 404:
                raise ModelNotFoundError(f"Model not found: {error_msg}")
            if status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded after {self.max_retries} retries: {error_msg}"
                )
            if status_code in (402, 403):
                raise QuotaError(f"Billing or quota issue: {error_msg}")
            if status_code == 401:
                raise AuthenticationError(f"Invalid API key: {error_msg}")
            raise ProviderTransientError(f"OpenRouter API error [{status_code}]: {error_msg}")

        # Handle network errors
        if (
            isinstance(error, asyncio.TimeoutError)
            or "timeout" in error_msg_lower
            or "timed out" in error_msg_lower
        ):
            should_retry = retry_count < self.max_retries
            if should_retry:
                delay = self.retry_delay * (2 ** retry_count)
                logger.info(
                    "Timeout error - retrying after %ss (attempt %s/%s)...",
                    delay,
                    retry_count + 1,
                    self.max_retries,
                )
                await asyncio.sleep(delay)
                return await self.get_model_response(
                    model_name,
                    prompt,
                    system_prompt,
                    params,
                    retry_count + 1,
                    response_schema=response_schema,
                )

            raise QueryTimeoutError(
                f"Provider timeout after {self.max_retries} retries: {error_msg}"
            )

        if "json" in error_msg_lower or "connection" in error_msg_lower or "network" in error_msg_lower:
            should_retry = retry_count < self.max_retries
            if should_retry:
                delay = self.retry_delay * (2 ** retry_count)
                logger.info(
                    "Network error - retrying after %ss (attempt %s/%s)...",
                    delay,
                    retry_count + 1,
                    self.max_retries,
                )
                await asyncio.sleep(delay)
                return await self.get_model_response(
                    model_name,
                    prompt,
                    system_prompt,
                    params,
                    retry_count + 1,
                    response_schema=response_schema,
                )

            raise ProviderTransientError(
                f"Network error after {self.max_retries} retries: {error_msg}"
            )

        # Preserve explicit model-output failures without wrapping.
        if error_msg.startswith("Model "):
            raise InvalidModelOutputError(error_msg)

        raise ProviderTransientError(f"Failed to retrieve response: {error_msg}")
