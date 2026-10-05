"""The process-wide vision and embedding adapters, chosen by AI_PROVIDER on first use
(same pattern as blob.get_blob_store), and the search rerankers, one per vendor."""

import logging
from pathlib import Path

from google import genai

from kms.ai.fake import FakeEmbedder, FakeVision
from kms.ai.gemini import GeminiVision
from kms.ai.interfaces import RERANKER_NAMES, Embedder, Reranker, RerankerName, Vision
from kms.ai.jev import JevReranker, build_jev_client
from kms.ai.noop import NoOpReranker
from kms.ai.recorded import RecordedEmbedder, RecordedVision
from kms.ai.voyage import VoyageClients, VoyageEmbedder, VoyageReranker
from kms.config import get_settings

logger = logging.getLogger(__name__)

_vision: Vision | None = None
_embedder: Embedder | None = None
# Built on first use, one per reranker name.
_rerankers: dict[RerankerName, Reranker] = {}
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


def available_rerankers() -> list[RerankerName]:
    """Say which rerankers give a relevance in this deployment.

    Returns:
        The names, in the order of RERANKER_NAMES, of the rerankers that are on: RERANK_ENABLED
        is true, AI_PROVIDER is "real", and the vendor's key is set (VOYAGE_API_KEY for "voyage",
        JEV_API_KEY for "jev"). Empty while reranking is off. Never raises.
    """
    settings = get_settings()
    if not settings.rerank_enabled or settings.ai_provider != "real":
        return []
    keys: dict[RerankerName, str | None] = {
        "voyage": settings.voyage_api_key,
        "jev": settings.jev_api_key,
    }
    return [name for name in RERANKER_NAMES if keys[name]]


def get_reranker(name: RerankerName) -> Reranker:
    """Return the shared reranker of one vendor, building it from settings on first use.

    Args:
        name: "voyage" or "jev".

    Returns:
        VoyageReranker over RERANK_MODEL, or JevReranker over JEV_MODEL, when that reranker is
        among `available_rerankers()`; otherwise NoOpReranker, which gives no relevance.

    Raises:
        typesafe_sdk.TypeSafeError: JEV_API_KEY is set but malformed.
    """
    global _voyage_clients
    reranker = _rerankers.get(name)
    if reranker is None:
        settings = get_settings()
        if name not in available_rerankers():
            reranker = NoOpReranker()
            logger.info("ai_adapters_selected reranker=%s model=none", name)
        elif name == "voyage":
            if _voyage_clients is None:
                _voyage_clients = VoyageClients(settings.voyage_api_key)
            reranker = VoyageReranker(_voyage_clients, settings.rerank_model)
            logger.info("ai_adapters_selected reranker=voyage model=%s", settings.rerank_model)
        else:
            client = build_jev_client(settings.jev_api_key)
            reranker = JevReranker(client, settings.jev_model, settings.jev_parallel_calls)
            logger.info("ai_adapters_selected reranker=jev model=%s", settings.jev_model)
        _rerankers[name] = reranker
    return reranker


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


def set_reranker(name: RerankerName, reranker: Reranker | None) -> None:
    """Replace the shared reranker of one vendor; tests use it.

    Args:
        name: "voyage" or "jev".
        reranker: The reranker to use, or None so the next call builds one from settings.
    """
    if reranker is None:
        _rerankers.pop(name, None)
    else:
        _rerankers[name] = reranker
