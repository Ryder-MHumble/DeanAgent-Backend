"""OpenRouter LLM service for business data enrichment."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


async def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    json_mode: bool = False,
) -> str:
    """
    Call OpenRouter API for LLM completion.

    Args:
        prompt: User message content.
        system_prompt: System instruction.
        model: Model ID (defaults to settings.OPENROUTER_MODEL).
        temperature: Sampling temperature.
        max_tokens: Maximum response tokens.
        json_mode: If True, request JSON output format.

    Returns:
        The assistant's response text.

    Raises:
        LLMError: If the API call fails after retries.
    """
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY not configured")

    model = model or settings.OPENROUTER_MODEL

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://information-crawler.local",
        "X-Title": "Information Crawler",
    }

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    OPENROUTER_API_URL,
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                if not content:
                    raise LLMError(f"Empty response from model {model}")
                return content

        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                import asyncio
                wait = 2 ** attempt
                logger.warning("Rate limited, waiting %ds...", wait)
                await asyncio.sleep(wait)
                continue
            raise LLMError(f"HTTP {e.response.status_code}: {e.response.text}") from e

        except httpx.RequestError as e:
            last_error = e
            logger.warning("Request error (attempt %d): %s", attempt + 1, e)
            import asyncio
            await asyncio.sleep(1)
            continue

    raise LLMError(f"Failed after 3 attempts: {last_error}")


async def call_llm_json(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4000,
) -> dict[str, Any] | list[Any]:
    """
    Call LLM and parse the response as JSON.

    Returns parsed JSON (dict or list).
    """
    raw = await call_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Failed to parse LLM response as JSON: {e}\nRaw: {text[:500]}") from e


class LLMError(Exception):
    """Raised when LLM service call fails."""
