"""The process-wide vision and embedding adapters, chosen by AI_PROVIDER on first use
(same pattern as blob.get_blob_store)."""

import logging

import voyageai
from google import genai
from google.genai import types

from kms.ai.fake import FakeEmbedder, FakeVision
from kms.ai.gemini import GEMINI_REQUEST_TIMEOUT_SECONDS, GeminiVision
from kms.ai.interfaces import Embedder, Vision
from kms.ai.voyage import VOYAGE_REQUEST_TIMEOUT_SECONDS, VoyageEmbedder
from kms.config import get_settings

logger = logging.getLogger(__name__)

_vision: Vision | None = None
_embedder: Embedder | None = None


def get_vision() -> Vision:
    """Return the shared vision adapter, building it from settings on first use.

    Returns:
        FakeVision when AI_PROVIDER is "fake"; GeminiVision over VISION_MODELS when it is "real".

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
            # when to try again. The SDK takes the timeout in milliseconds.
            client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(timeout=GEMINI_REQUEST_TIMEOUT_SECONDS * 1000),
            )
            _vision = GeminiVision(client, settings.vision_models)
            logger.info("ai_adapters_selected provider=real vision=%s", settings.vision_models)
        else:
            _vision = FakeVision()
            logger.info("ai_adapters_selected provider=fake vision=%s", _vision.model)
    return _vision


def get_embedder() -> Embedder:
    """Return the shared embedder, building it from settings on first use.

    Returns:
        FakeEmbedder with EMBEDDING_DIMS dimensions when AI_PROVIDER is "fake"; VoyageEmbedder
        over EMBEDDING_MODEL with EMBEDDING_DIMS dimensions when it is "real".

    Raises:
        ValueError: AI_PROVIDER is "real" and VOYAGE_API_KEY is not set.
    """
    global _embedder
    if _embedder is None:
        settings = get_settings()
        if settings.ai_provider == "real":
            if not settings.voyage_api_key:
                raise ValueError("VOYAGE_API_KEY is not set")
            # max_retries=0: the SDK's own retries stay off, so only our backoff decides when to
            # try again.
            client = voyageai.Client(
                api_key=settings.voyage_api_key,
                max_retries=0,
                timeout=VOYAGE_REQUEST_TIMEOUT_SECONDS,
            )
            _embedder = VoyageEmbedder(client, settings.embedding_model, settings.embedding_dims)
            logger.info("ai_adapters_selected provider=real embedder=%s", settings.embedding_model)
        else:
            _embedder = FakeEmbedder(settings.embedding_dims)
            logger.info("ai_adapters_selected provider=fake embedder=%s", _embedder.model)
    return _embedder


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
