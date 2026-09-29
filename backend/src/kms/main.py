"""App factory. The built SPA (if present) is served for every non-API path."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kms.api import app_config, assets, collections, health, search
from kms.api.auth import require_password
from kms.config import get_settings
from kms.ingest.pool import WorkerPool
from kms.logs import configure_logging

logger = logging.getLogger(__name__)


def flatten_validation_error(
    request: Request, validation_error: RequestValidationError
) -> JSONResponse:
    """Turn FastAPI's validation errors into the API's single-string `detail`.

    FastAPI reports invalid input as a list of error objects; the API promises one string.

    Args:
        request: The failing request; unused, but part of FastAPI's handler signature.
        validation_error: The error FastAPI raised for the invalid input.

    Returns:
        A 422 response whose `detail` joins every "field: message" with "; ".
    """
    messages = []
    for error in validation_error.errors():
        # The location ends with the parameter's name, e.g. ("query", "collection").
        field = error["loc"][-1]
        messages.append(f"{field}: {error['msg']}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run the worker pool for as long as the app serves, when `worker_enabled` is on.

    Args:
        app: The app being started; unused, but part of FastAPI's lifespan signature.

    Yields:
        Nothing; the app serves requests while this is suspended at `yield`.
    """
    settings = get_settings()
    if not settings.worker_enabled:
        yield
        return
    pool = WorkerPool(settings.worker_threads)
    pool.start()
    try:
        yield
    finally:
        pool.stop()


def create_app() -> FastAPI:
    """Build the app: the API routers, plus the built SPA when `static_dir` holds one."""
    configure_logging()
    app = FastAPI(title="KMS", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, flatten_validation_error)
    # The middleware added last runs first, so the password is checked before the upload size.
    app.middleware("http")(assets.reject_oversized_upload)
    app.middleware("http")(require_password)
    app.include_router(health.router)
    app.include_router(assets.router)
    app.include_router(collections.router)
    app.include_router(search.router)
    app.include_router(app_config.router)

    settings = get_settings()
    static = settings.static_dir
    index = static / "index.html"
    logger.info(
        "app_started ui=%s worker=%s",
        "built" if index.exists() else "none",
        "on" if settings.worker_enabled else "off",
    )
    if index.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="spa-assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            """Serve a file of the built SPA, or `index.html` so the SPA's router takes the path."""
            # Without it the browser may reuse a cached page without asking the server, so the
            # password prompt never shows and every API call then fails. "no-cache" still lets it
            # keep the file, but it must check with the server, and so pass the password, first.
            headers = {"Cache-Control": "no-cache"}
            # The path comes from the URL, where "%2e%2e" arrives as "..", so a path that resolves
            # outside the build is treated as unknown rather than served.
            file = (static / path).resolve()
            inside_build = file.is_relative_to(static.resolve())
            if path and inside_build and file.is_file():
                return FileResponse(file, headers=headers)
            return FileResponse(index, headers=headers)

    return app


app = create_app()
