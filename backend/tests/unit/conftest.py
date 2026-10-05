import pytest

import kms.ai
from kms.ai import set_embedder, set_vision
from kms.config import get_settings


@pytest.fixture
def vendor_providers(monkeypatch):
    # The settings and the adapters are cached per process, so both are reset on the way in
    # and on the way out; otherwise a vendor adapter would leak into the next test. The reranker
    # has no setter, so its cached value is swapped out here and put back by monkeypatch.
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "voyage")
    monkeypatch.setenv("RERANK_PROVIDER", "none")
    # Recording off, so the tests see the vendor adapters themselves; a test turns it on.
    monkeypatch.setenv("AI_CACHE_DIR", "")
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)
    monkeypatch.setattr(kms.ai, "_reranker", None)
    yield
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)
