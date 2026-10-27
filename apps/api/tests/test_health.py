import pytest
from app.main import create_app
from fastapi.testclient import TestClient


def test_live_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unready"}


def test_unreachable_database_is_safe(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://probe:private@127.0.0.1:1/absent"
    )
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "private" not in response.text
        assert client.get("/health/live").status_code == 200


@pytest.mark.integration
@pytest.mark.parametrize("damage", ["shared", "file", "symlink"])
def test_unusable_private_storage_is_unready_without_details(database, monkeypatch, tmp_path, damage):
    sources, renders = tmp_path / "originals", tmp_path / "renders"
    monkeypatch.setenv("VISION_SOURCE_ROOT", str(sources))
    monkeypatch.setenv("VISION_RENDER_ROOT", str(renders))
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.get("/health/ready").json() == {"status": "ready"}
        if damage == "shared":
            renders.chmod(0o755)
        elif damage == "file":
            sources.rmdir()
            sources.write_bytes(b"")
        else:
            (tmp_path / "elsewhere").mkdir(mode=0o700)
            sources.rmdir()
            sources.symlink_to(tmp_path / "elsewhere")
        response = client.get("/health/ready")
        assert (response.status_code, response.json()) == (503, {"status": "unready"})
        assert str(tmp_path) not in response.text


def test_trusted_hosts_default_to_loopback_and_can_name_the_packaged_service(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app(), base_url="http://api:8000") as client:
        assert client.get("/health/live").status_code == 400
    monkeypatch.setenv("VISION_TRUSTED_HOSTS", "api,127.0.0.1,localhost")
    with TestClient(create_app(), base_url="http://api:8000") as client:
        assert client.get("/health/live").json() == {"status": "alive"}
    with TestClient(create_app(), base_url="http://elsewhere.example") as client:
        assert client.get("/health/live").status_code == 400
