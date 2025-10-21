def test_health_ok(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert "time" in data

