import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

# Load .env once when module is imported
load_dotenv()


@lru_cache(maxsize=1)
def get_openai_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_xai_api_key() -> Optional[str]:
    # Use only XAI_API_KEY for xAI provider
    return os.getenv("XAI_API_KEY")


@lru_cache(maxsize=1)
def get_xai_base_url() -> str:
    # Default xAI API base URL; allow override for proxies/self-hosted gateways
    return os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")


@lru_cache(maxsize=1)
def get_llm_provider() -> str:
    val = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    # Normalize alias "grok" to canonical provider name "xai"
    if val == "grok":
        return "xai"
    return val


@lru_cache(maxsize=1)
def is_llm_configured() -> bool:
    provider = get_llm_provider()
    if provider == "openai":
        key = get_openai_api_key() or ""
        return key.strip() != ""
    if provider == "xai":
        key = get_xai_api_key() or ""
        return key.strip() != ""
    # Unknown provider → not configured
    return False


@lru_cache(maxsize=1)
def get_chroma_host() -> str:
    return os.getenv("CHROMA_HOST", "localhost")


@lru_cache(maxsize=1)
def get_chroma_port() -> int:
    try:
        return int(os.getenv("CHROMA_PORT", "8000"))
    except ValueError:
        return 8000


@lru_cache(maxsize=1)
def get_chroma_tenant() -> str:
    return os.getenv("CHROMA_TENANT", "default_tenant")


@lru_cache(maxsize=1)
def get_chroma_database() -> str:
    return os.getenv("CHROMA_DATABASE", "default_database")


@lru_cache(maxsize=1)
def get_redis_url() -> Optional[str]:
    return os.getenv("REDIS_URL")


# =============================
# External databases (storage)
# =============================


@lru_cache(maxsize=1)
def get_timescale_dsn() -> Optional[str]:
    return os.getenv("TIMESCALE_DSN", "postgresql://user:pass@localhost:5432/memories")


# =============================
# Extraction-related settings
# =============================


@lru_cache(maxsize=1)
def get_extraction_model_name() -> str:
    # Provider-aware default: OpenAI → gpt-5, xAI → grok-4-fast-reasoning
    env_val = os.getenv("EXTRACTION_MODEL")
    if env_val and env_val.strip() != "":
        return env_val
    provider = get_llm_provider()
    if provider == "openai":
        env_val = os.getenv("EXTRACTION_MODEL_OPENAI")
        if env_val and env_val.strip() != "":
            return env_val
        return "gpt-5"
    if provider in {"xai", "grok"}:  # accept alias "grok" for backward compatibility
        env_val = os.getenv("EXTRACTION_MODEL_XAI")
        if env_val and env_val.strip() != "":
            return env_val
        return "grok-4-fast-reasoning"
    return "gpt-5"


@lru_cache(maxsize=1)
def get_embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")


@lru_cache(maxsize=1)
def get_aggressive_mode() -> bool:
    return os.getenv("EXTRACTION_AGGRESSIVE", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@lru_cache(maxsize=1)
def get_worthy_threshold() -> float:
    default_val = 0.35 if get_aggressive_mode() else 0.55
    try:
        return float(os.getenv("WORTHY_THRESHOLD", str(default_val)))
    except ValueError:
        return default_val


@lru_cache(maxsize=1)
def get_type_threshold() -> float:
    try:
        return float(os.getenv("TYPE_THRESHOLD", "0.5"))
    except ValueError:
        return 0.5


@lru_cache(maxsize=1)
def get_layer_threshold() -> float:
    try:
        return float(os.getenv("LAYER_THRESHOLD", "0.5"))
    except ValueError:
        return 0.5


@lru_cache(maxsize=1)
def get_default_short_term_ttl_seconds() -> int:
    try:
        return int(os.getenv("SHORT_TERM_TTL_SECONDS", "3600"))
    except ValueError:
        return 3600


@lru_cache(maxsize=1)
def get_default_next_action_ttl_hours() -> int:
    try:
        return int(os.getenv("NEXT_ACTION_TTL_HOURS", "48"))
    except ValueError:
        return 48


@lru_cache(maxsize=1)
def get_max_memories_per_request() -> int:
    try:
        return int(os.getenv("MAX_MEMORIES_PER_REQUEST", "10"))
    except ValueError:
        return 10


@lru_cache(maxsize=1)
def get_extraction_timeouts_ms() -> int:
    try:
        return int(os.getenv("EXTRACTION_TIMEOUT_MS", "180000"))
    except ValueError:
        return 180000


@lru_cache(maxsize=1)
def get_extraction_retries() -> int:
    try:
        return int(os.getenv("EXTRACTION_RETRIES", "1"))
    except ValueError:
        return 1


@lru_cache(maxsize=1)
def get_heuristic_only_mode() -> bool:
    return os.getenv("EXTRACTION_HEURISTIC_ONLY", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@lru_cache(maxsize=1)
def get_disable_heuristics() -> bool:
    # When true, heuristic extraction is hard-disabled (used to force LLM-only).
    # Tests can override via env to re-enable heuristics.
    return os.getenv("EXTRACTION_DISABLE_HEURISTICS", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@lru_cache(maxsize=1)
def is_scheduled_maintenance_enabled() -> bool:
    """Control daily scheduled maintenance (compaction) via env.

    Primary flag: SCHEDULED_MAINTENANCE_ENABLED (default: true)
    Legacy alias supported: SCHEDULED_EXTRACTION_ENABLED
    """
    val = os.getenv("SCHEDULED_MAINTENANCE_ENABLED")
    if val is None:
        alias = os.getenv("SCHEDULED_EXTRACTION_ENABLED")
        if alias is None:
            return True
        return alias.strip().lower() in {"1", "true", "yes", "on"}
    return val.strip().lower() in {"1", "true", "yes", "on"}


# Langfuse Configuration
def get_langfuse_public_key() -> str:
    """Get Langfuse public key from environment."""
    return os.getenv("LANGFUSE_PUBLIC_KEY", "")


def get_langfuse_secret_key() -> str:
    """Get Langfuse secret key from environment."""
    return os.getenv("LANGFUSE_SECRET_KEY", "")


def get_langfuse_host() -> str:
    """Get Langfuse host URL from environment."""
    return os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")


def is_langfuse_enabled() -> bool:
    """Check if Langfuse tracing is enabled."""
    return bool(get_langfuse_public_key() and get_langfuse_secret_key())
