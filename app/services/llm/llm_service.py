"""OpenRouter LLM service for business data enrichment."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.services.llm.llm_call_tracker import get_tracker

logger = logging.getLogger(__name__)

_DEFAULT_PROVIDER_ORDER = ("openrouter", "siliconflow")
_provider_order: list[str] = list(_DEFAULT_PROVIDER_ORDER)
_provider_order_date: date | None = None


def _current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _reset_provider_order_if_needed() -> None:
    global _provider_order_date, _provider_order
    today = _current_utc_date()
    if _provider_order_date != today:
        _provider_order = list(_DEFAULT_PROVIDER_ORDER)
        _provider_order_date = today


def _promote_provider(provider: str) -> None:
    global _provider_order
    if provider not in _provider_order:
        return
    _provider_order = [provider, *[p for p in _provider_order if p != provider]]


def has_llm_provider_configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY or settings.SILICONFLOW_API_KEY)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _extract_provider_cost_usd(data: dict[str, Any]) -> float | None:
    """Best-effort extraction of provider-reported cost from OpenRouter response."""
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}

    candidates = [
        usage.get("cost"),
        usage.get("cost_usd"),
        usage.get("total_cost"),
        usage.get("total_cost_usd"),
        data.get("cost"),
        data.get("cost_usd"),
        data.get("total_cost"),
        data.get("total_cost_usd"),
    ]

    for candidate in candidates:
        parsed = _safe_float(candidate)
        if parsed is not None and parsed >= 0:
            return parsed
    return None


def _resolve_provider_sequence() -> list[dict[str, str]]:
    _reset_provider_order_if_needed()

    providers: dict[str, dict[str, str]] = {}
    if settings.OPENROUTER_API_KEY:
        providers["openrouter"] = {
            "name": "openrouter",
            "api_key": settings.OPENROUTER_API_KEY,
            "api_url": settings.OPENROUTER_API_URL,
            "model": settings.OPENROUTER_MODEL,
        }
    if settings.SILICONFLOW_API_KEY:
        providers["siliconflow"] = {
            "name": "siliconflow",
            "api_key": settings.SILICONFLOW_API_KEY,
            "api_url": settings.SILICONFLOW_API_URL,
            "model": settings.SILICONFLOW_MODEL,
        }

    ordered: list[dict[str, str]] = []
    for provider in _provider_order:
        if provider in providers:
            ordered.append(providers[provider])

    return ordered


def _resolve_model_for_provider(
    model: str | dict[str, str] | None,
    provider: dict[str, str],
) -> str:
    if isinstance(model, dict):
        configured = str(model.get(provider["name"], "") or "").strip()
        return configured or provider["model"]
    if isinstance(model, str):
        configured = model.strip()
        return configured or provider["model"]
    return provider["model"]


async def _call_provider_once(
    provider: str,
    api_url: str,
    api_key: str,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any], float | None]:
    model = str(payload.get("model") or "")
    timeout_secs = 180.0 if "pro" in model.lower() else 60.0

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://information-crawler.local"
        headers["X-Title"] = "Intelligence Engine Backend Services"

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                resp = await client.post(
                    api_url,
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                if not content:
                    raise LLMError(
                        f"Empty response from model {model} via provider {provider}"
                    )

                usage = data.get("usage", {})
                return content, usage, _extract_provider_cost_usd(data)

        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                import asyncio

                wait = 2**attempt
                logger.warning(
                    "%s rate limited, waiting %ds...",
                    provider,
                    wait,
                )
                await asyncio.sleep(wait)
                continue
            raise LLMError(
                f"{provider} HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            last_error = e
            logger.warning("%s request error (attempt %d): %s", provider, attempt + 1, e)
            import asyncio

            await asyncio.sleep(1)
            continue

    raise LLMError(f"{provider} failed after 3 attempts: {last_error}")


async def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str | dict[str, str] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    json_mode: bool = False,
    *,
    stage: str = "general",
    article_id: str | None = None,
    article_title: str | None = None,
    source_id: str | None = None,
    dimension: str | None = None,
) -> str:
    """
    Call configured LLM API with daily provider priority and auto-fallback.

    Args:
        prompt: User message content.
        system_prompt: System instruction.
        model: Model ID or provider-specific model map.
        temperature: Sampling temperature.
        max_tokens: Maximum response tokens.
        json_mode: If True, request JSON output format.
        stage: Pipeline stage for tracking (policy, personnel, tech_frontier, etc.).
        article_id: Article/URL hash for reference.
        article_title: Article title for audit trail.
        source_id: News source ID.
        dimension: Data dimension.

    Returns:
        The assistant's response text.

    Raises:
        LLMError: If the API call fails after retries.
    """
    if not has_llm_provider_configured():
        raise LLMError(
            "No LLM provider configured (requires OPENROUTER_API_KEY or SILICONFLOW_API_KEY)"
        )

    providers = _resolve_provider_sequence()
    if not providers:
        raise LLMError(
            "No active LLM provider available (requires OPENROUTER_API_KEY or SILICONFLOW_API_KEY)"
        )

    tracker = get_tracker()
    start_time = time.time()

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model or "",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    errors: list[str] = []
    for idx, provider in enumerate(providers):
        selected_model = _resolve_model_for_provider(model, provider)
        payload["model"] = selected_model

        try:
            content, usage, provider_cost = await _call_provider_once(
                provider["name"],
                provider["api_url"],
                provider["api_key"],
                payload,
            )
            tracker.log_call(
                model=selected_model,
                provider=provider["name"],
                prompt=prompt,
                system_prompt=system_prompt,
                response_text=content,
                input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage.get("completion_tokens", 0) or 0),
                stage=stage,
                article_id=article_id,
                article_title=article_title,
                source_id=source_id,
                dimension=dimension,
                duration_ms=(time.time() - start_time) * 1000,
                success=True,
                provider_cost_usd=provider_cost,
            )

            if idx > 0:
                _promote_provider(provider["name"])
                logger.warning(
                    "Provider switched to %s for the rest of %s",
                    provider["name"],
                    _current_utc_date(),
                )
            return content
        except LLMError as e:
            error_msg = str(e)
            errors.append(error_msg)
            tracker.log_call(
                model=selected_model,
                provider=provider["name"],
                prompt=prompt,
                system_prompt=system_prompt,
                response_text="",
                input_tokens=0,
                output_tokens=0,
                stage=stage,
                article_id=article_id,
                article_title=article_title,
                source_id=source_id,
                dimension=dimension,
                duration_ms=(time.time() - start_time) * 1000,
                success=False,
                error_message=error_msg,
            )
            logger.warning("LLM provider %s failed: %s", provider["name"], error_msg)

    raise LLMError("All configured LLM providers failed: " + " | ".join(errors))


async def call_llm_json(
    prompt: str,
    system_prompt: str = "",
    model: str | dict[str, str] | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4000,
    *,
    stage: str = "general",
    article_id: str | None = None,
    article_title: str | None = None,
    source_id: str | None = None,
    dimension: str | None = None,
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
        stage=stage,
        article_id=article_id,
        article_title=article_title,
        source_id=source_id,
        dimension=dimension,
    )

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Failed to parse LLM response as JSON: {e}\\nRaw: {text[:500]}") from e


class LLMError(Exception):
    """Raised when LLM service call fails."""
