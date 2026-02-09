from __future__ import annotations

from typing import Any, Dict, Optional

import json
import logging
import re

from src.config import (
    get_extraction_model_name,
    get_extraction_retries,
    get_extraction_timeouts_ms,
    get_llm_provider,
    get_openai_api_key,
    get_xai_api_key,
    get_xai_base_url,
)


EXTRACTION_MODEL = get_extraction_model_name()


def _parse_json_from_text(text: str, expect_array: bool) -> Any:
    """Best-effort parse JSON from LLM text.

    Handles code fences (```json ... ```), leading/trailing prose, and extracts the
    first complete JSON object/array if needed. Falls back to [] or {}.
    """
    if not text or text.strip() == "":
        return [] if expect_array else {}

    candidate = text.strip()

    # 1) Strip code fences if present
    code_block = re.search(r"```(?:json)?\s*([\s\S]+?)```", candidate, re.IGNORECASE)
    if code_block:
        candidate = code_block.group(1).strip()

    # 2) Try direct parse
    try:
        parsed = json.loads(candidate)
        # Coerce to expected container shape
        if expect_array:
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                if isinstance(parsed.get("items"), list):
                    return parsed["items"]
                # As a last resort, if dict values look like items, return list(values)
                vals = list(parsed.values())
                return vals if vals else []
            return []
        return parsed
    except Exception:
        pass

    # 3) Extract bracketed JSON region (array preferred when expect_array)
    if expect_array and "[" in candidate and "]" in candidate:
        start = candidate.find("[")
        end = candidate.rfind("]")
        if start != -1 and end != -1 and end > start:
            frag = candidate[start : end + 1]
            try:
                parsed = json.loads(frag)
                if expect_array:
                    return parsed if isinstance(parsed, list) else []
                return parsed
            except Exception:
                pass

    if "{" in candidate and "}" in candidate:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            frag = candidate[start : end + 1]
            try:
                parsed = json.loads(frag)
                if expect_array:
                    return parsed if isinstance(parsed, list) else []
                return parsed
            except Exception:
                pass

    # 4) Fallback: empty structure to avoid hard failure in pipeline
    return [] if expect_array else {}


def _call_llm_json(
    system_prompt: str, user_payload: Dict[str, Any], *, expect_array: bool = False
) -> Optional[Any]:
    """Call LLM and parse JSON response. Uses Langfuse OpenAI wrapper for auto-instrumentation."""
    from src.config import is_langfuse_enabled

    logger = logging.getLogger("extraction")
    provider = get_llm_provider()

    try:
        timeout_s = max(1, get_extraction_timeouts_ms() // 1000)
        retries = max(0, get_extraction_retries())
        last_exc: Optional[Exception] = None

        if provider == "openai":
            api_key = (get_openai_api_key() or "").strip()
            if not api_key:
                return None

            # Use Langfuse OpenAI wrapper for auto-instrumentation if enabled
            if is_langfuse_enabled():
                try:
                    from langfuse.openai import OpenAI  # type: ignore
                except ImportError:
                    from openai import OpenAI  # type: ignore
            else:
                from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=api_key)
            for _ in range(retries + 1):
                try:
                    resp = client.chat.completions.create(
                        model=EXTRACTION_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(user_payload)},
                        ],
                        response_format=None
                        if expect_array
                        else {"type": "json_object"},
                        timeout=timeout_s,
                    )
                    text = resp.choices[0].message.content or (
                        "[]" if expect_array else "{}"
                    )
                    logger.info(
                        "LLM call ok | provider=openai model=%s | expect_array=%s | payload=%s | output=%s",
                        EXTRACTION_MODEL,
                        expect_array,
                        json.dumps(user_payload)[:1000],
                        text[:1000],
                    )
                    return _parse_json_from_text(text, expect_array)
                except Exception as exc:  # retry
                    last_exc = exc
                    continue

        elif provider == "xai":
            api_key = (get_xai_api_key() or "").strip()
            if not api_key:
                return None

            # xAI uses OpenAI-compatible API with custom base_url
            # Langfuse wrapper supports base_url parameter
            if is_langfuse_enabled():
                try:
                    from langfuse.openai import OpenAI  # type: ignore
                except ImportError:
                    from openai import OpenAI  # type: ignore
            else:
                from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=api_key, base_url=get_xai_base_url())
            for _ in range(retries + 1):
                try:
                    resp = client.chat.completions.create(
                        model=EXTRACTION_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(user_payload)},
                        ],
                        response_format=None
                        if expect_array
                        else {"type": "json_object"},
                        timeout=max(timeout_s, 180),
                    )
                    text = resp.choices[0].message.content or (
                        "[]" if expect_array else "{}"
                    )
                    logger.info(
                        "LLM call ok | provider=xai model=%s | expect_array=%s | payload=%s | output=%s",
                        EXTRACTION_MODEL,
                        expect_array,
                        json.dumps(user_payload)[:1000],
                        text[:1000],
                    )
                    return _parse_json_from_text(text, expect_array)
                except Exception as exc:  # retry
                    last_exc = exc
                    continue
        else:
            logger.error("Unknown LLM provider: %s", provider)
            return None

        if last_exc:
            raise last_exc
    except Exception as exc:
        logger.exception(
            "LLM call failed | provider=%s model=%s | expect_array=%s | payload=%s",
            provider,
            EXTRACTION_MODEL,
            expect_array,
            json.dumps(user_payload)[:1000],
        )
        # Trace the error for debugging
        from src.services.tracing import trace_error

        trace_error(
            exc,
            metadata={
                "provider": provider,
                "model": EXTRACTION_MODEL,
                "expect_array": expect_array,
                "context": "llm_extraction",
            },
        )
        return None


def _normalize_llm_content(content: str, source_text: str) -> str:
    """
    DEPRECATED: This function is deprecated as of the enhanced extraction prompt.
    The LLM now handles content normalization directly in the EXTRACTION_PROMPT.

    This function is kept for backward compatibility but should not be used.
    The extraction pipeline now relies on LLM-based normalization.
    """
    # For backward compatibility, return content as-is since LLM handles normalization
    return content
