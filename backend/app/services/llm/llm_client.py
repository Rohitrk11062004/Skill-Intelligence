from __future__ import annotations

import asyncio
import logging
from time import monotonic
from typing import Any

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - handled in offline/test environments
    genai = None

from app.core.config import settings

log = logging.getLogger(__name__)
_PREVIEW_MAX_CHARS = 500


def _estimated_tokens(text: str) -> int:
    # Lightweight approximation: ~4 chars per token for English text.
    return max(1, len(text) // 4) if text else 0


def _truncate_preview(text: str, limit: int = _PREVIEW_MAX_CHARS) -> str:
    clean = str(text or "")
    if len(clean) <= limit:
        return clean
    return clean[:limit]


def _usage_metadata(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None

    # Gemini usage metadata can be a plain object; serialize known token fields only.
    fields = [
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
    ]
    payload: dict[str, Any] = {}
    for field in fields:
        value = getattr(usage, field, None)
        if value is not None:
            payload[field] = value

    return payload or None


def _get_model():
    if genai is None:
        raise ValueError("google.generativeai is not available in this environment")
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.gemini_model)


async def gemini_generate(*, purpose: str, prompt: str, user_id: str | None = None, request_id: str | None = None) -> str:
    prompt_text = str(prompt or "")
    started = monotonic()
    llm_started = started

    log_payload: dict[str, Any] = {
        "purpose": str(purpose or "unknown"),
        "model": settings.gemini_model,
        "prompt_chars": len(prompt_text),
        "prompt_estimated_tokens": _estimated_tokens(prompt_text),
        "ok": False,
    }
    if user_id:
        log_payload["user_id"] = str(user_id)
    if request_id:
        log_payload["request_id"] = str(request_id)

    try:
        model = _get_model()
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt_text),
            timeout=max(1, int(getattr(settings, "llm_timeout_seconds", 30) or 30)),
        )
        llm_ms = (monotonic() - llm_started) * 1000

        response_text = getattr(response, "text", "") or ""
        usage = _usage_metadata(response)

        log_payload.update(
            {
                "ok": True,
                "response_chars": len(response_text),
                "response_estimated_tokens": _estimated_tokens(response_text),
                "llm_ms": round(llm_ms, 2),
                "total_ms": round((monotonic() - started) * 1000, 2),
            }
        )
        if usage:
            log_payload["usage"] = usage

        if settings.llm_log_payloads:
            log_payload["prompt_preview"] = _truncate_preview(prompt_text)
            log_payload["response_preview"] = _truncate_preview(response_text)

        log.info("llm_call: %s", log_payload)
        return str(response_text)
    except Exception as exc:
        log_payload.update(
            {
                "ok": False,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "llm_ms": round((monotonic() - llm_started) * 1000, 2),
                "total_ms": round((monotonic() - started) * 1000, 2),
            }
        )

        if settings.llm_log_payloads:
            log_payload["prompt_preview"] = _truncate_preview(prompt_text)

        log.error("llm_call: %s", log_payload)
        raise
