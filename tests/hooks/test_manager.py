import asyncio

from src.hooks.base import WebhookEnvelope
from src.hooks.manager import HookManager
from src.hooks.pipeline import NormalizationPipeline
from src.hooks.settings import HookSettings, HooksConfig


def test_manager_consent_and_webhook():
    class FakePool:
        def __init__(self):
            self.storage: dict[tuple[str, str], dict] = {}

        class _ConnCtx:
            def __init__(self, storage: dict[tuple[str, str], dict]):
                self._storage = storage

            def __enter__(self):
                return FakePool._Connection(self._storage)

            def __exit__(self, exc_type, exc, tb):
                return False

        class _Connection:
            def __init__(self, storage: dict[tuple[str, str], dict]):
                self._storage = storage

            class _Cursor:
                def __init__(self, storage: dict[tuple[str, str], dict]):
                    self._storage = storage
                    self._rows = None

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def execute(self, query, params):  # type: ignore[no-untyped-def]
                    normalized = " ".join(str(query).split())
                    if normalized.startswith("INSERT INTO hook_consents"):
                        payload = params["payload"]
                        if hasattr(payload, "obj"):
                            payload = payload.obj
                        stored = dict(payload) if isinstance(payload, dict) else payload
                        self._storage[(params["hook_name"], params["user_id"])] = stored
                        self._rows = None
                    elif normalized.startswith("SELECT payload"):
                        key = (params["hook_name"], params["user_id"])
                        payload = self._storage.get(key)
                        self._rows = {"payload": payload} if payload is not None else None
                    elif normalized.startswith("SELECT user_id, payload"):
                        hook_entries = [
                            {"user_id": user, "payload": payload}
                            for (hook, user), payload in self._storage.items()
                            if hook == params["hook_name"]
                        ]
                        self._rows = hook_entries
                    elif normalized.startswith("DELETE FROM hook_consents"):
                        key = (params["hook_name"], params["user_id"])
                        self._storage.pop(key, None)
                        self._rows = None

                def fetchone(self):  # type: ignore[no-untyped-def]
                    if isinstance(self._rows, list):
                        return self._rows[0] if self._rows else None
                    return self._rows

                def fetchall(self):  # type: ignore[no-untyped-def]
                    if isinstance(self._rows, list):
                        return self._rows
                    return [self._rows] if self._rows else []

            def cursor(self):
                return FakePool._Connection._Cursor(self._storage)

            def commit(self):
                return None

        def connection(self):
            return FakePool._ConnCtx(self.storage)

    async def run():
        config = HooksConfig(
            enabled=True,
            hooks=[HookSettings(name="gmail", kind="gmail", enabled=True, poll_interval_seconds=30, error_backoff_seconds=5)],
        )
        manager = HookManager(config=config, redis_client=None, postgres_pool=FakePool())

        recorded = {}

        async def fake_ingestion(request):  # type: ignore[no-untyped-def]
            recorded["user"] = request.user_id
            return {"ok": True}

        manager._pipeline = NormalizationPipeline(redis_client=None, ingestion_runner=fake_ingestion)
        await manager.start(start_pollers=False)

        manager.save_consent("gmail", "user-1", {"seed_messages": [{"id": "msg-seed", "subject": "Welcome"}]})

        hook = manager._hooks["gmail"]
        seed_events = await hook.poll_once()
        assert seed_events and seed_events[0].payload["subject"] == "Welcome"

        envelope = WebhookEnvelope(user_id="user-1", event_id="evt-1", payload={"historyId": "123"})
        accepted = await manager.handle_webhook("gmail", envelope)
        assert accepted is True
        assert recorded["user"] == "user-1"

        await manager.stop()

    asyncio.run(run())
