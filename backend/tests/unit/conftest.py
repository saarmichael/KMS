import pytest

from kms.ai import set_embedder, set_vision
from kms.config import get_settings


@pytest.fixture
def real_provider(monkeypatch):
    # The settings and the adapters are cached per process, so both are reset on the way in
    # and on the way out; otherwise the real provider would leak into the next test.
    monkeypatch.setenv("AI_PROVIDER", "real")
    # Recording off, so the tests see the real adapters themselves; a test turns it on.
    monkeypatch.setenv("AI_CACHE_DIR", "")
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)
    yield
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)
