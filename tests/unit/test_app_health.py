class _RedisFailing:
    def ping(self) -> bool:
        return False


def test_health_endpoint_basic(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_full_reports_failures(api_client, monkeypatch):
    monkeypatch.setattr("src.app.ping_timescale", lambda: (False, "down"))
    monkeypatch.setattr("src.app.get_redis_client", lambda: _RedisFailing())
    monkeypatch.setattr("src.app.ping_neo4j", lambda: (True, None))
    monkeypatch.setattr("src.dependencies.timescale.get_timescale_conn", lambda: None)

    response = api_client.get("/health/full")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "degraded"
    assert data["checks"]["timescale"] == {"ok": False, "error": "down"}
    assert data["checks"]["redis"]["ok"] is False
