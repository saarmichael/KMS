import pytest

from kms.config import get_settings

PASSWORD = "harbour-lights"


@pytest.fixture
def password_set(monkeypatch):
    # The settings are cached per process, so the cache is cleared on the way in and out;
    # otherwise the password would leak into other tests.
    monkeypatch.setenv("APP_PASSWORD", PASSWORD)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_everything_is_open_when_no_password_is_set(client):
    assert client.get("/api/collections").status_code == 200


def test_request_without_password_gets_401_and_a_challenge(password_set, client):
    response = client.get("/api/collections")
    assert response.status_code == 401
    assert response.json() == {"detail": "Password required"}
    assert response.headers["WWW-Authenticate"].startswith("Basic ")


def test_wrong_password_gets_401(password_set, client):
    response = client.get("/api/collections", auth=("anyone", "wrong-password"))
    assert response.status_code == 401


def test_right_password_passes(password_set, client):
    response = client.get("/api/collections", auth=("anyone", PASSWORD))
    assert response.status_code == 200


def test_health_is_open_with_a_password_set(password_set, client):
    assert client.get("/api/health").status_code == 200
