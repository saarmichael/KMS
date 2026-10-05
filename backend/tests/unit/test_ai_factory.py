import typing

import pytest
from pydantic import ValidationError

from kms.ai import (
    EMBEDDER_BUILDERS,
    RERANKER_BUILDERS,
    VISION_BUILDERS,
    get_embedder,
    get_reranker,
    get_vision,
    set_embedder,
    set_vision,
)
from kms.ai.fake import FakeEmbedder, FakeVision
from kms.ai.gemini import GeminiVision
from kms.ai.noop import NoOpReranker
from kms.ai.recorded import RecordedEmbedder, RecordedVision
from kms.ai.voyage import VoyageEmbedder, VoyageReranker
from kms.config import Settings, get_settings


def test_every_provider_name_has_a_builder():
    fields = Settings.model_fields
    vision_names = typing.get_args(fields["vision_provider"].annotation)
    embedding_names = typing.get_args(fields["embedding_provider"].annotation)
    rerank_names = typing.get_args(fields["rerank_provider"].annotation)

    assert set(vision_names) == set(VISION_BUILDERS)
    assert set(embedding_names) == set(EMBEDDER_BUILDERS)
    assert set(rerank_names) == set(RERANKER_BUILDERS)


def test_unknown_provider_is_refused(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    with pytest.raises(ValidationError, match="embedding_provider"):
        Settings(_env_file=None)


def test_retired_ai_provider_is_refused(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "real")
    with pytest.raises(ValidationError, match="VISION_PROVIDER, EMBEDDING_PROVIDER"):
        Settings(_env_file=None)


def test_retired_rerank_enabled_is_refused(monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    with pytest.raises(ValidationError, match="RERANK_PROVIDER"):
        Settings(_env_file=None)


def test_fake_providers_need_no_keys(vendor_providers, monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("RERANK_PROVIDER", "none")
    # Empty in the environment, so the keys in .env cannot fill them in.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    get_settings.cache_clear()

    assert isinstance(get_vision(), FakeVision)
    assert isinstance(get_embedder(), FakeEmbedder)
    assert isinstance(get_reranker(), NoOpReranker)


def test_gemini_vision_is_built_from_settings(vendor_providers, monkeypatch):
    # A dummy key: building the client makes no call.
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("VISION_MODELS", '["first-model", "second-model"]')
    get_settings.cache_clear()

    vision = get_vision()

    assert isinstance(vision, GeminiVision)
    assert vision.models == ["first-model", "second-model"]
    assert vision.model == "first-model"


def test_missing_gemini_key_is_refused(vendor_providers, monkeypatch):
    # Empty in the environment, so a key in .env cannot fill it in.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_vision()


def test_voyage_embedder_is_built_from_settings(vendor_providers, monkeypatch):
    # A dummy key: building the client makes no call.
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    get_settings.cache_clear()

    embedder = get_embedder()

    assert isinstance(embedder, VoyageEmbedder)
    assert embedder.model == get_settings().embedding_model
    assert embedder.dims == get_settings().embedding_dims
    assert embedder.parallel_calls == get_settings().embed_parallel_calls


def test_missing_voyage_key_is_refused(vendor_providers, monkeypatch):
    # Empty in the environment, so a key in .env cannot fill it in.
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
        get_embedder()


def test_roles_choose_independently(vendor_providers, monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "fake")
    # No Gemini key, so the fake vision must not need one.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    get_settings.cache_clear()

    assert isinstance(get_vision(), FakeVision)
    assert isinstance(get_embedder(), VoyageEmbedder)


def test_voyage_reranker_works_without_a_real_embedder(vendor_providers, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("RERANK_PROVIDER", "voyage")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    get_settings.cache_clear()

    reranker = get_reranker()

    assert isinstance(reranker, VoyageReranker)
    assert reranker.model == get_settings().rerank_model
    assert isinstance(get_embedder(), FakeEmbedder)


def test_embedder_and_reranker_share_voyage_clients(vendor_providers, monkeypatch):
    monkeypatch.setenv("RERANK_PROVIDER", "voyage")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    get_settings.cache_clear()

    assert get_embedder().clients is get_reranker().clients


def test_recording_wraps_a_vendor_but_not_the_fake(vendor_providers, monkeypatch, tmp_path):
    # Dummy keys: building the clients makes no call.
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setenv("AI_CACHE_DIR", str(tmp_path))
    get_settings.cache_clear()
    assert isinstance(get_vision(), RecordedVision)
    assert isinstance(get_embedder(), RecordedEmbedder)

    monkeypatch.setenv("VISION_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)
    assert isinstance(get_vision(), FakeVision)
    assert isinstance(get_embedder(), FakeEmbedder)
