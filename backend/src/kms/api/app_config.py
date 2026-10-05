from fastapi import APIRouter

from kms.ai import available_rerankers
from kms.api.schemas import AppConfig
from kms.config import get_settings

router = APIRouter()


@router.get("/api/config")
def app_config() -> AppConfig:
    """The deployment settings the UI shapes itself by: whether this is a demo, and which
    rerankers it can offer."""
    settings = get_settings()
    return AppConfig(
        demo_mode=settings.demo_mode,
        rerankers=available_rerankers(),
        default_reranker=settings.default_reranker,
    )
