from fastapi.testclient import TestClient

from src.app import app


client = TestClient(app)


def test_health_ok():
	response = client.get("/health")
	assert response.status_code == 200
	data = response.json()
	assert data.get("status") == "ok"
	assert "time" in data

