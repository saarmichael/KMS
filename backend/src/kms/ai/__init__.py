"""The process-wide vision and embedding adapters, chosen by AI_PROVIDER on first use
(same pattern as blob.get_blob_store), and the search reranker."""

import logging
from pathlib import Path

from google import genai

from kms.ai.fake import FakeEmbedder, FakeVision
from kms.ai.gemini import GeminiVision
from kms.ai.interfaces import Embedder, Reranker, Vision
from kms.ai.noop import NoOpReranker
from kms.ai.recorded import RecordedEmbedder, RecordedVision
from kms.ai.voyage import VoyageClients, VoyageEmbedder, VoyageReranker
from kms.config import get_settings

logger = logging.getLogger(__name__)

_vision: Vision | None = None
_embedder: Embedder | None = None
_reranker: Reranker | None = None
# One set of Voyage clients for the embedder and the reranker, so a timeout's client is built once.
_voyage_clients: VoyageClients | None = None


def get_vision() -> Vision:
    """Return the shared vision adapter, building it from settings on first use.

    Returns:
        FakeVision when AI_PROVIDER is "fake"; GeminiVision over VISION_MODELS when it is "real",
        wrapped in RecordedVision when AI_CACHE_DIR is set.

    Raises:
        ValueError: AI_PROVIDER is "real" and GEMINI_API_KEY is not set.
    """
    global _vision
    if _vision is None:
        settings = get_settings()
        if settings.ai_provider == "real":
            if not settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is not set")
            # No retry_options: the SDK's own retries stay off, so only our backoff decides
            # when to try again. No timeout either: each request takes its caller's.
            client = genai.Client(api_key=settings.gemini_api_key)
            gemini_vision = GeminiVision(client, settings.vision_models)
            if settings.ai_cache_dir:
                _vision = RecordedVision(gemini_vision, Path(settings.ai_cache_dir))
            else:
                _vision = gemini_vision
            logger.info("ai_adapters_selected provider=real vision=%s", settings.vision_models)
        else:
            _vision = FakeVision()
            logger.info("ai_adapters_selected provider=fake vision=%s", _vision.model)
    return _vision


def get_embedder() -> Embedder:
    """Return the shared embedder, building it from settings on first use.

    Returns:
        FakeEmbedder with EMBEDDING_DIMS dimensions when AI_PROVIDER is "fake"; VoyageEmbedder
        over EMBEDDING_MODEL with EMBEDDING_DIMS dimensions when it is "real", wrapped in
        RecordedEmbedder when AI_CACHE_DIR is set.

    Raises:
        ValueError: AI_PROVIDER is "real" and VOYAGE_API_KEY is not set.
    """
    global _embedder, _voyage_clients
    if _embedder is None:
        settings = get_settings()
        if settings.ai_provider == "real":
            if not settings.voyage_api_key:
                raise ValueError("VOYAGE_API_KEY is not set")
            if _voyage_clients is None:
                _voyage_clients = VoyageClients(settings.voyage_api_key)
            voyage_embedder = VoyageEmbedder(
                _voyage_clients,
                settings.embedding_model,
                settings.embedding_dims,
                settings.embed_parallel_calls,
            )
            if settings.ai_cache_dir:
                _embedder = RecordedEmbedder(voyage_embedder, Path(settings.ai_cache_dir))
            else:
                _embedder = voyage_embedder
            logger.info("ai_adapters_selected provider=real embedder=%s", settings.embedding_model)
        else:
            _embedder = FakeEmbedder(settings.embedding_dims)
            logger.info("ai_adapters_selected provider=fake embedder=%s", _embedder.model)
    return _embedder


def get_reranker() -> Reranker:
    """Return the shared reranker that scores the top search results, building it from settings
    on first use.

    Returns:
        VoyageReranker over RERANK_MODEL when RERANK_ENABLED is true and AI_PROVIDER is "real";
        otherwise NoOpReranker, which gives no relevance.

    Raises:
        ValueError: The Voyage reranker is chosen and VOYAGE_API_KEY is not set.
    """
    global _reranker, _voyage_clients
    if _reranker is None:
        settings = get_settings()
        if settings.rerank_enabled and settings.ai_provider == "real":
            if not settings.voyage_api_key:
                raise ValueError("VOYAGE_API_KEY is not set")
            if _voyage_clients is None:
                _voyage_clients = VoyageClients(settings.voyage_api_key)
            _reranker = VoyageReranker(_voyage_clients, settings.rerank_model)
            logger.info("ai_adapters_selected provider=real reranker=%s", settings.rerank_model)
        else:
            _reranker = NoOpReranker()
            logger.info("ai_adapters_selected reranker=none")
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
