import asyncio
from datetime import datetime, timezone

from src.hooks.base import HookEvent
from src.hooks.pipeline import NormalizationPipeline


def test_email_normalization_and_dedupe():
    async def run():
        captured: dict[str, object] = {}

        async def fake_ingestion(request):  # type: ignore[no-untyped-def]
            captured["request"] = request
            return {"memories_created": 0}

        pipeline = NormalizationPipeline(redis_client=None, ingestion_runner=fake_ingestion)
        event = HookEvent(
            event_id="email-1",
            user_id="user-123",
            category="email",
            source="gmail",
            payload={
                "subject": "Team sync",
                "from": "alice@example.com",
                "to": ["bob@example.com"],
                "body": "Agenda: review quarterly plan",
                "id": "msg-001",
                "labels": ["INBOX"],
            },
            occurred_at=datetime(2024, 8, 1, 10, 30, tzinfo=timezone.utc),
        )

        result = await pipeline.process(event)
        assert result == {"memories_created": 0}
        request = captured["request"]
        assert request.user_id == "user-123"
        assert request.history[0].content.startswith("Email subject: Team sync")
        assert request.metadata["hook_category"] == "email"

        duplicate = await pipeline.process(event)
        assert duplicate is None

    asyncio.run(run())


def test_calendar_normalization():
    async def run():
        recorded = {}

        async def fake_ingestion(request):  # type: ignore[no-untyped-def]
            recorded["history"] = [m.content for m in request.history]
            return {"stored": True}

        pipeline = NormalizationPipeline(redis_client=None, ingestion_runner=fake_ingestion)
        event = HookEvent(
            event_id="cal-1",
            user_id="user-456",
            category="calendar",
            source="google_calendar",
            payload={
                "id": "evt-001",
                "summary": "Product review",
                "start": {"dateTime": "2024-08-02T15:00:00Z"},
                "end": {"dateTime": "2024-08-02T16:00:00Z"},
                "attendees": [{"email": "carol@example.com"}],
                "location": "Zoom",
            },
            occurred_at=datetime(2024, 8, 2, 15, 0, tzinfo=timezone.utc),
        )

        result = await pipeline.process(event)
        assert result == {"stored": True}
        assert "Product review" in recorded["history"][0]

    asyncio.run(run())
