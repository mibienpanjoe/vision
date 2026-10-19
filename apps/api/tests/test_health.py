from fastapi.testclient import TestClient

from app.main import create_app


def test_live_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unready"}


def test_unreachable_database_is_safe(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://probe:private@127.0.0.1:1/absent")
    with TestClient(create_app()) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "private" not in response.text
        assert client.get("/health/live").status_code == 200
