"""The process-wide vision adapter, embedder and search reranker, each built on first use by the
provider its setting names: VISION_PROVIDER, EMBEDDING_PROVIDER and RERANK_PROVIDER (same pattern
as blob.get_blob_store)."""

import logging
from collections.abc import Callable
from pathlib import Path

from kms.ai.fake import build_fake_embedder, build_fake_vision
from kms.ai.gemini import build_gemini_vision
from kms.ai.interfaces import Embedder, Reranker, Vision
from kms.ai.noop import build_noop_reranker
from kms.ai.recorded import RecordedEmbedder, RecordedVision
from kms.ai.voyage import build_voyage_embedder, build_voyage_reranker
from kms.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Provider name to builder, one table per role, so that adding a vendor is one line here and the
# getters below never change.
VISION_BUILDERS: dict[str, Callable[[Settings], Vision]] = {
    "fake": build_fake_vision,
    "gemini": build_gemini_vision,
}
EMBEDDER_BUILDERS: dict[str, Callable[[Settings], Embedder]] = {
    "fake": build_fake_embedder,
    "voyage": build_voyage_embedder,
}
RERANKER_BUILDERS: dict[str, Callable[[Settings], Reranker]] = {
    "none": build_noop_reranker,
    "voyage": build_voyage_reranker,
}

_vision: Vision | None = None
_embedder: Embedder | None = None
_reranker: Reranker | None = None


def get_vision() -> Vision:
    """Return the shared vision adapter, building it from settings on first use.

    Returns:
        The adapter built by VISION_PROVIDER's builder. Unless the provider is "fake", it is
        wrapped in RecordedVision when AI_CACHE_DIR is set.

    Raises:
        ValueError: The builder refused the settings, for example a missing API key.
    """
    global _vision
    if _vision is None:
        settings = get_settings()
        provider = settings.vision_provider
        vision = VISION_BUILDERS[provider](settings)
        # The fake answers instantly and for free, so recording it would only fill the folder.
        if settings.ai_cache_dir and provider != "fake":
            vision = RecordedVision(vision, Path(settings.ai_cache_dir))
        _vision = vision
        logger.info(
            "ai_adapter_selected role=%s provider=%s model=%s", "vision", provider, vision.model
        )
    return _vision


def get_embedder() -> Embedder:
    """Return the shared embedder, building it from settings on first use.

    Returns:
        The embedder built by EMBEDDING_PROVIDER's builder. Unless the provider is "fake", it is
        wrapped in RecordedEmbedder when AI_CACHE_DIR is set.

    Raises:
        ValueError: The builder refused the settings, for example a missing API key.
    """
    global _embedder
    if _embedder is None:
        settings = get_settings()
        provider = settings.embedding_provider
        embedder = EMBEDDER_BUILDERS[provider](settings)
        # The fake answers instantly and for free, so recording it would only fill the folder.
        if settings.ai_cache_dir and provider != "fake":
            embedder = RecordedEmbedder(embedder, Path(settings.ai_cache_dir))
        _embedder = embedder
        logger.info(
            "ai_adapter_selected role=%s provider=%s model=%s",
            "embedding",
            provider,
            embedder.model,
        )
    return _embedder


def get_reranker() -> Reranker:
    """Return the shared reranker that scores the top search results, building it from settings
    on first use.

    Returns:
        The reranker built by RERANK_PROVIDER's builder; never recorded. With "none" it is
        NoOpReranker, which gives no relevance.

    Raises:
        ValueError: The builder refused the settings, for example a missing API key.
    """
    global _reranker
    if _reranker is None:
        settings = get_settings()
        provider = settings.rerank_provider
        _reranker = RERANKER_BUILDERS[provider](settings)
        # A reranker carries no model id of its own, and "none" asks no model at all.
        if provider == "none":
            model = "none"
        else:
            model = settings.rerank_model
        logger.info("ai_adapter_selected role=%s provider=%s model=%s", "rerank", provider, model)
    return _reranker


def set_vision(vision: Vision | None) -> None:
    """Replace the shared vision adapter; tests use it.

    Args:
        vision: The adapter to use, or None so the next call builds one from settings.
    """
    global _vision
    _vision = vision


def set_embedder(embedder: Embedder | None) -> None:
    """Replace the shared embedder; tests use it.

    Args:
        embedder: The embedder to use, or None so the next call builds one from settings.
    """
    global _embedder
    _embedder = embedder
