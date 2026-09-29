import pytest
from fastapi.testclient import TestClient

from kms.config import get_settings
from kms.main import create_app


@pytest.fixture
def spa_client(monkeypatch, tmp_path):
    # A build folder with one file, and a secret beside it that must never be served.
    build = tmp_path / "build"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("the index page")
    (build / "favicon.svg").write_text("the favicon")
    (tmp_path / "secret.txt").write_text("the secret")
    monkeypatch.setenv("STATIC_DIR", str(build))
    monkeypatch.setenv("WORKER_ENABLED", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_spa_serves_a_file_of_the_build(spa_client):
    response = spa_client.get("/favicon.svg")

    assert response.status_code == 200
    assert response.text == "the favicon"


def test_spa_never_serves_a_file_outside_the_build(spa_client):
    # The encoded dots reach the route as "..", as they do through uvicorn.
    response = spa_client.get("/%2e%2e/secret.txt")

    assert response.status_code == 200
    assert response.text == "the index page"
