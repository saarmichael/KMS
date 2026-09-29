from fastapi import APIRouter

from kms.api.schemas import AppConfig
from kms.config import get_settings

router = APIRouter()


@router.get("/api/config")
def app_config() -> AppConfig:
    """The deployment settings the UI shapes itself by: for now, whether this is a demo."""
    return AppConfig(demo_mode=get_settings().demo_mode)
