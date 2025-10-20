"""Configuration models for hook integrations."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class HookSettings(BaseModel):
    """Per-hook configuration options loaded from ``hooks.yml``."""

    name: str
    kind: str
    enabled: bool = True
    poll_interval_seconds: int = Field(default=120, ge=5, le=3600)
    error_backoff_seconds: int = Field(default=30, ge=5, le=900)
    scopes: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "kind")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class HooksConfig(BaseModel):
    """Top-level hook configuration."""

    enabled: bool = True
    hooks: List[HookSettings] = Field(default_factory=list)

    def is_enabled(self, name: str) -> bool:
        hook = next((h for h in self.hooks if h.name == name), None)
        return bool(hook and hook.enabled)


DEFAULT_CONFIG_PATH = Path("config/hooks.yml")


@lru_cache(maxsize=1)
def load_hooks_config(path: Optional[str] = None) -> HooksConfig:
    """Load ``HooksConfig`` from disk, returning defaults if missing."""

    resolved = Path(path or os.getenv("HOOKS_CONFIG_PATH", DEFAULT_CONFIG_PATH)).expanduser()
    if not resolved.exists():
        return HooksConfig(enabled=False, hooks=[])
    with resolved.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return HooksConfig.model_validate(data)


__all__ = ["HookSettings", "HooksConfig", "load_hooks_config"]
