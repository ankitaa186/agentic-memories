from fastapi.testclient import TestClient

from src.app import app


client = TestClient(app)


def test_store_stub():
	payload = {
		"user_id": "user-123",
		"history": [{"role": "user", "content": "I love sci-fi books."}],
	}
	resp = client.post("/v1/store", json=payload)
	assert resp.status_code == 200
	data = resp.json()
	assert data["memories_created"] >= 1
	assert isinstance(data["ids"], list)


def test_retrieve_stub():
	resp = client.get("/v1/retrieve", params={"query": "sci-fi", "limit": 5})
	assert resp.status_code == 200
	data = resp.json()
	assert "results" in data and isinstance(data["results"], list)
	assert "pagination" in data


def test_health_full_structure():
	resp = client.get("/health/full")
	assert resp.status_code == 200
	data = resp.json()
	assert "status" in data
	assert "checks" in data and isinstance(data["checks"], dict)

