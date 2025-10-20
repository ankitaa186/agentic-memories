import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

# Load .env once when module is imported. `override=True` ensures that local
# development values defined in .env always take precedence over environment
# variables populated by GitHub Actions secrets or the host system.
load_dotenv(override=True)


def _get_raw_env(name: str) -> Optional[str]:
    """Return the raw environment value for ``name``.

    The lookup order is:
    1. Regular environment variable (includes GitHub Secrets that map directly)
    2. ``GITHUB_SECRET_<NAME>`` – explicit prefix for secrets if a workflow
       exports them with that naming convention.
    """

    if name in os.environ:
        return os.environ[name]
    prefixed = f"GITHUB_SECRET_{name}"
    if prefixed in os.environ:
        return os.environ[prefixed]
    return None


def get_env_value(name: str, default: Optional[str] = None) -> Optional[str]:
    """Fetch an environment value honouring GitHub secrets and defaults."""

    value = _get_raw_env(name)
    if value is None:
        return default
    return value


def _get_bool_env(name: str, default: str = "false") -> bool:
    value = get_env_value(name)
    if value is None:
        value = default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: str) -> int:
    value = get_env_value(name)
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return int(default)


def _get_float_env(name: str, default: str) -> float:
    value = get_env_value(name)
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


@lru_cache(maxsize=1)
def get_openai_api_key() -> Optional[str]:
    return get_env_value("OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_xai_api_key() -> Optional[str]:
    # Use only XAI_API_KEY for xAI provider
    return get_env_value("XAI_API_KEY")


@lru_cache(maxsize=1)
def get_xai_base_url() -> str:
    # Default xAI API base URL; allow override for proxies/self-hosted gateways
    return get_env_value("XAI_BASE_URL", "https://api.x.ai/v1") or "https://api.x.ai/v1"


@lru_cache(maxsize=1)
def get_llm_provider() -> str:
    val = (get_env_value("LLM_PROVIDER", "openai") or "openai").strip().lower()
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
    return get_env_value("CHROMA_HOST", "localhost") or "localhost"


@lru_cache(maxsize=1)
def get_chroma_port() -> int:
    return _get_int_env("CHROMA_PORT", "8000")


@lru_cache(maxsize=1)
def get_chroma_tenant() -> str:
    return get_env_value("CHROMA_TENANT", "default_tenant") or "default_tenant"


@lru_cache(maxsize=1)
def get_chroma_database() -> str:
    return get_env_value("CHROMA_DATABASE", "default_database") or "default_database"


@lru_cache(maxsize=1)
def get_redis_url() -> Optional[str]:
    return get_env_value("REDIS_URL")


# =============================
# External databases (storage)
# =============================


@lru_cache(maxsize=1)
def get_timescale_dsn() -> Optional[str]:
    return get_env_value("TIMESCALE_DSN", "postgresql://user:pass@localhost:5432/memories") or "postgresql://user:pass@localhost:5432/memories"


@lru_cache(maxsize=1)
def get_neo4j_uri() -> Optional[str]:
    return get_env_value("NEO4J_URI", "bolt://localhost:7687") or "bolt://localhost:7687"


@lru_cache(maxsize=1)
def get_neo4j_user() -> Optional[str]:
    return get_env_value("NEO4J_USER", "neo4j") or "neo4j"


@lru_cache(maxsize=1)
def get_neo4j_password() -> Optional[str]:
    return get_env_value("NEO4J_PASSWORD", "password") or "password"


# =============================
# Extraction-related settings
# =============================


@lru_cache(maxsize=1)
def get_extraction_model_name() -> str:
    # Provider-aware default: OpenAI → gpt-5, xAI → grok-4-fast-reasoning
    env_val = get_env_value("EXTRACTION_MODEL")
    if env_val and env_val.strip() != "":
        return env_val
    provider = get_llm_provider()
    if provider == "openai":
        env_val = get_env_value("EXTRACTION_MODEL_OPENAI")
        if env_val and env_val.strip() != "":
            return env_val
        return "gpt-5"
    if provider in {"xai", "grok"}:  # accept alias "grok" for backward compatibility
        env_val = get_env_value("EXTRACTION_MODEL_XAI")
        if env_val and env_val.strip() != "":
            return env_val
        return "grok-4-fast-reasoning"
    return "gpt-5"


@lru_cache(maxsize=1)
def get_embedding_model_name() -> str:
    return get_env_value("EMBEDDING_MODEL", "text-embedding-3-large") or "text-embedding-3-large"


@lru_cache(maxsize=1)
def get_aggressive_mode() -> bool:
        return _get_bool_env("EXTRACTION_AGGRESSIVE", "true")


@lru_cache(maxsize=1)
def get_worthy_threshold() -> float:
        default_val = 0.35 if get_aggressive_mode() else 0.55
        try:
                return float(get_env_value("WORTHY_THRESHOLD", str(default_val)) or str(default_val))
        except ValueError:
                return default_val


@lru_cache(maxsize=1)
def get_type_threshold() -> float:
        return _get_float_env("TYPE_THRESHOLD", "0.5")


@lru_cache(maxsize=1)
def get_layer_threshold() -> float:
        return _get_float_env("LAYER_THRESHOLD", "0.5")


@lru_cache(maxsize=1)
def get_default_short_term_ttl_seconds() -> int:
        return _get_int_env("SHORT_TERM_TTL_SECONDS", "3600")


@lru_cache(maxsize=1)
def get_default_next_action_ttl_hours() -> int:
        return _get_int_env("NEXT_ACTION_TTL_HOURS", "48")


@lru_cache(maxsize=1)
def get_max_memories_per_request() -> int:
        return _get_int_env("MAX_MEMORIES_PER_REQUEST", "10")


@lru_cache(maxsize=1)
def get_extraction_timeouts_ms() -> int:
        return _get_int_env("EXTRACTION_TIMEOUT_MS", "180000")


@lru_cache(maxsize=1)
def get_extraction_retries() -> int:
        return _get_int_env("EXTRACTION_RETRIES", "1")


@lru_cache(maxsize=1)
def get_heuristic_only_mode() -> bool:
        return _get_bool_env("EXTRACTION_HEURISTIC_ONLY", "false")


@lru_cache(maxsize=1)
def get_disable_heuristics() -> bool:
        # When true, heuristic extraction is hard-disabled (used to force LLM-only).
        # Tests can override via env to re-enable heuristics.
        return _get_bool_env("EXTRACTION_DISABLE_HEURISTICS", "true")


@lru_cache(maxsize=1)
def is_scheduled_maintenance_enabled() -> bool:
	"""Control daily scheduled maintenance (compaction) via env.

	Primary flag: SCHEDULED_MAINTENANCE_ENABLED (default: true)
	Legacy alias supported: SCHEDULED_EXTRACTION_ENABLED
	"""
        val = get_env_value("SCHEDULED_MAINTENANCE_ENABLED")
        if val is None:
                alias = get_env_value("SCHEDULED_EXTRACTION_ENABLED")
                if alias is None:
                        return True
                return alias.strip().lower() in {"1", "true", "yes", "on"}
        return val.strip().lower() in {"1", "true", "yes", "on"}


# Langfuse Configuration
def get_langfuse_public_key() -> str:
        """Get Langfuse public key from environment."""
        return get_env_value("LANGFUSE_PUBLIC_KEY", "") or ""


def get_langfuse_secret_key() -> str:
        """Get Langfuse secret key from environment."""
        return get_env_value("LANGFUSE_SECRET_KEY", "") or ""


def get_langfuse_host() -> str:
        """Get Langfuse host URL from environment."""
        return get_env_value("LANGFUSE_HOST", "https://us.cloud.langfuse.com") or "https://us.cloud.langfuse.com"


def is_langfuse_enabled() -> bool:
	"""Check if Langfuse tracing is enabled."""
	return bool(get_langfuse_public_key() and get_langfuse_secret_key())
