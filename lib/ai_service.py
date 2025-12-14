"""
AI Service - Arsenal Module
OpenRouter client with retry logic and dual API support
Copy-paste ready: Just provide config
"""

import asyncio
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
import logging

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 4
INITIAL_RETRY_DELAY = 2  # seconds


class AIService:
    """AI Service for OpenRouter API with exponential backoff retry"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        referer: str = "http://localhost:8000",
        app_name: str = "AI Research Tool"
    ):
        if not api_key:
            raise ValueError("API key is required")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": referer,
                "X-Title": app_name
            }
        )

    async def get_model_response(
        self,
        model_name: str,
        prompt: str,
        system_prompt: str = "",
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> str:
        """
        Get model response with automatic retry logic

        Args:
            model_name: Model identifier
            prompt: User prompt
            system_prompt: Optional system prompt for ethical priming
            params: Generation parameters
            retry_count: Current retry attempt (internal)

        Returns:
            Model response text
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

            # Dual API support: chat.completions (with system) vs responses.create (legacy)
            if system_prompt and system_prompt.strip():
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]

                try:
                    response = await self.client.chat.completions.create(
                        **request_params,
                        messages=messages
                    )
                except Exception as api_error:
                    if "JSON" in str(api_error):
                        logger.error(f"JSON parsing error - API may have returned HTML or empty response")
                        logger.error(f"Model: {model_name}, Retry count: {retry_count}")
                    raise

                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()

                return "The model returned an empty response."
            else:
                # Legacy responses.create API (no system prompt)
                # Note: OpenRouter may not support this endpoint for all models
                # Fallback to chat.completions without system message
                messages = [{"role": "user", "content": prompt}]

                try:
                    response = await self.client.chat.completions.create(
                        **request_params,
                        messages=messages
                    )
                except Exception as api_error:
                    if "JSON" in str(api_error):
                        logger.error(f"JSON parsing error - API may have returned HTML or empty response")
                        logger.error(f"Model: {model_name}, Retry count: {retry_count}")
                    raise

                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()

                return "The model returned an empty response."

        except Exception as error:
            return await self._handle_error(error, model_name, prompt, system_prompt, params, retry_count)

    async def _handle_error(
        self,
        error: Exception,
        model_name: str,
        prompt: str,
        system_prompt: str,
        params: Dict[str, Any],
        retry_count: int
    ) -> str:
        """Handle errors with retry logic"""
        logger.error(f"Error querying OpenRouter: {error}")

        # Check for status code in error
        status_code = getattr(error, 'status_code', None)
        error_msg = str(error)

        if status_code:
            # Retry on 429 (rate limit) or 5xx (server errors)
            should_retry = (status_code == 429 or status_code >= 500) and retry_count < MAX_RETRIES

            if should_retry:
                delay = INITIAL_RETRY_DELAY * (2 ** retry_count)
                logger.info(f"Retrying after {delay}s (attempt {retry_count + 1}/{MAX_RETRIES})...")
                await asyncio.sleep(delay)
                return await self.get_model_response(model_name, prompt, system_prompt, params, retry_count + 1)

            # Add context based on status code
            if status_code == 404:
                raise Exception(f"Model not found: {error_msg}")
            elif status_code == 429:
                raise Exception(f"Rate limit exceeded after {MAX_RETRIES} retries: {error_msg}")
            elif status_code in (402, 403):
                raise Exception(f"Billing or authentication issue: {error_msg}")
            elif status_code == 401:
                raise Exception(f"Invalid API key: {error_msg}")
            else:
                raise Exception(f"OpenRouter API error ({status_code}): {error_msg}")

        # Handle network errors
        if "JSON" in error_msg or "Connection" in error_msg:
            should_retry = retry_count < MAX_RETRIES
            if should_retry:
                delay = INITIAL_RETRY_DELAY * (2 ** retry_count)
                logger.info(f"Network error - retrying after {delay}s (attempt {retry_count + 1}/{MAX_RETRIES})...")
                await asyncio.sleep(delay)
                return await self.get_model_response(model_name, prompt, system_prompt, params, retry_count + 1)

            raise Exception(f"API error after {MAX_RETRIES} retries: {error_msg}")

        raise Exception(f"Failed to retrieve response: {error_msg}")
