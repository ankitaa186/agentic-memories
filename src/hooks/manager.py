"""Hook manager orchestrates lifecycle, consent, and routing."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from psycopg.types.json import Json

from src.dependencies.redis_client import get_redis_client
from src.dependencies.timescale import get_timescale_pool

from .base import Hook, WebhookEnvelope
from .pipeline import NormalizationPipeline
from .settings import HookSettings, HooksConfig, load_hooks_config
from . import registry


logger = logging.getLogger("agentic_memories.hooks.consent")


class HookConsentStore:
    """Persist user consent tokens in PostgreSQL with in-memory fallback."""

    def __init__(self, pool=None) -> None:
        self.pool = pool or get_timescale_pool()
        self._memory: Dict[str, Dict[str, Dict[str, Any]]] = {}
        if self.pool is None:
            logger.warning("timescale/postgres pool unavailable; using in-memory consent store")

    def _execute(self, query: str, params: Dict[str, Any], *, fetch: Optional[str] = None):
        if self.pool is None:
            raise RuntimeError("PostgreSQL pool is not configured")
        with self.pool.connection() as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch == "one":
                    row = cur.fetchone()
                elif fetch == "all":
                    row = cur.fetchall()
                else:
                    row = None
                conn.commit()
        return row

    def save(self, hook_name: str, user_id: str, payload: Dict[str, Any]) -> None:
        if self.pool is None:
            self._memory.setdefault(hook_name, {})[user_id] = dict(payload)
            return
        params = {
            "hook_name": hook_name,
            "user_id": user_id,
            "payload": Json(payload or {}),
        }
        self._execute(
            """
            INSERT INTO hook_consents (hook_name, user_id, payload)
            VALUES (%(hook_name)s, %(user_id)s, %(payload)s)
            ON CONFLICT (hook_name, user_id) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = NOW()
            """,
            params,
        )

    def get(self, hook_name: str, user_id: str) -> Optional[Dict[str, Any]]:
        if self.pool is None:
            payload = self._memory.get(hook_name, {}).get(user_id)
            return dict(payload) if payload is not None else None
        row = self._execute(
            """
            SELECT payload
            FROM hook_consents
            WHERE hook_name = %(hook_name)s
              AND user_id = %(user_id)s
            """,
            {"hook_name": hook_name, "user_id": user_id},
            fetch="one",
        )
        if not row:
            return None
        payload = row.get("payload")  # type: ignore[index]
        if hasattr(payload, "obj"):
            payload = payload.obj
        return dict(payload) if isinstance(payload, dict) else payload

    def delete(self, hook_name: str, user_id: str) -> None:
        if self.pool is None:
            if hook_name in self._memory:
                self._memory[hook_name].pop(user_id, None)
            return
        self._execute(
            """
            DELETE FROM hook_consents
            WHERE hook_name = %(hook_name)s
              AND user_id = %(user_id)s
            """,
            {"hook_name": hook_name, "user_id": user_id},
        )

    def list(self, hook_name: str) -> Dict[str, Dict[str, Any]]:
        if self.pool is None:
            return {user: dict(payload) for user, payload in self._memory.get(hook_name, {}).items()}
        rows = self._execute(
            """
            SELECT user_id, payload
            FROM hook_consents
            WHERE hook_name = %(hook_name)s
            """,
            {"hook_name": hook_name},
            fetch="all",
        )
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows or []:  # type: ignore[union-attr]
            payload = row.get("payload")  # type: ignore[index]
            if hasattr(payload, "obj"):
                payload = payload.obj
            if isinstance(payload, dict):
                result[row["user_id"]] = dict(payload)
            else:
                result[row["user_id"]] = payload
        return result


class HookStateStore:
    """Persist hook specific cursors/checkpoints."""

    def __init__(self, redis_client=None) -> None:
        self.redis = redis_client or get_redis_client()
        self._memory: Dict[str, Dict[str, Any]] = {}

    def _key(self, hook_name: str, user_id: str) -> str:
        return f"hooks:state:{hook_name}:{user_id}"

    def load(self, hook_name: str, user_id: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.redis is not None:
            raw = self.redis.get(self._key(hook_name, user_id))
            if raw:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    pass
        return dict(self._memory.get(hook_name, {}).get(user_id, default or {}))

    def save(self, hook_name: str, user_id: str, state: Dict[str, Any]) -> None:
        if self.redis is not None:
            self.redis.set(self._key(hook_name, user_id), json.dumps(state))
        else:
            self._memory.setdefault(hook_name, {})[user_id] = dict(state)


class HookManager:
    """Central orchestrator for hook lifecycle."""

    def __init__(
        self,
        *,
        config: Optional[HooksConfig] = None,
        config_path: Optional[str] = None,
        redis_client=None,
        postgres_pool=None,
    ) -> None:
        self.logger = logging.getLogger("agentic_memories.hooks.manager")
        self.config = config or load_hooks_config(config_path)
        self.redis = redis_client or get_redis_client()
        self._postgres_pool = postgres_pool or get_timescale_pool()
        self._pipeline = NormalizationPipeline(redis_client=self.redis)
        self.consent_store = HookConsentStore(self._postgres_pool)
        self.state_store = HookStateStore(redis_client)
        self._hooks: Dict[str, Hook] = {}
        self._running = False

    async def start(self, *, start_pollers: bool = True) -> None:
        if self._running or not self.config.enabled:
            if not self.config.enabled:
                self.logger.info("hook manager disabled via config")
            return
        self._running = True
        for hook_settings in self.config.hooks:
            if not hook_settings.enabled:
                self.logger.info("hook disabled | name=%s", hook_settings.name)
                continue
            hook = self._build_hook(hook_settings)
            if hook is None:
                continue
            self._hooks[hook_settings.name] = hook
            if start_pollers:
                await hook.start()
        self.logger.info("hook manager started | hooks=%s", list(self._hooks))

    async def stop(self) -> None:
        if not self._running:
            return
        for hook in self._hooks.values():
            await hook.stop()
        self._hooks.clear()
        self._running = False
        self.logger.info("hook manager stopped")

    def _build_hook(self, settings: HookSettings) -> Optional[Hook]:
        hook_cls = registry.resolve(settings.kind)
        if not hook_cls:
            self.logger.warning("unknown hook kind | kind=%s", settings.kind)
            return None
        hook = hook_cls(settings=settings, manager=self)
        return hook

    async def handle_webhook(self, hook_name: str, envelope: WebhookEnvelope) -> bool:
        hook = self._hooks.get(hook_name)
        if not hook:
            self.logger.warning("webhook for unknown hook | name=%s", hook_name)
            return False
        event = hook.transform_webhook(envelope)
        if not event:
            self.logger.info("webhook ignored by hook | name=%s", hook_name)
            return False
        await hook.emit(event)
        return True

    # Consent/state helpers exposed to hooks ---------------------------------
    @property
    def pipeline(self) -> NormalizationPipeline:
        return self._pipeline

    # Methods referenced by HookManagerProtocol
    def get_consent(self, hook_name: str, user_id: str) -> Optional[Dict[str, Any]]:
        return self.consent_store.get(hook_name, user_id)

    def list_consent(self, hook_name: str) -> Dict[str, Dict[str, Any]]:
        return self.consent_store.list(hook_name)

    def save_consent(self, hook_name: str, user_id: str, payload: Dict[str, Any]) -> None:
        self.consent_store.save(hook_name, user_id, payload)

    def delete_consent(self, hook_name: str, user_id: str) -> None:
        self.consent_store.delete(hook_name, user_id)

    def load_state(self, hook_name: str, user_id: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.state_store.load(hook_name, user_id, default)

    def save_state(self, hook_name: str, user_id: str, state: Dict[str, Any]) -> None:
        self.state_store.save(hook_name, user_id, state)

    def list_hooks(self) -> Dict[str, HookSettings]:
        return {settings.name: settings for settings in self.config.hooks}


def create_manager() -> HookManager:
    return HookManager()


__all__ = ["HookManager", "create_manager"]
