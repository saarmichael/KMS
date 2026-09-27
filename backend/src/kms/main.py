"""App factory. The built SPA (if present) is served for every non-API path."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kms.api import assets, collections, health
from kms.config import get_settings
from kms.logs import configure_logging


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


def create_app() -> FastAPI:
    """Build the app: the API routers, plus the built SPA when `static_dir` holds one."""
    configure_logging()
    app = FastAPI(title="KMS", version="0.1.0")
    app.add_exception_handler(RequestValidationError, flatten_validation_error)
    app.include_router(health.router)
    app.include_router(assets.router)
    app.include_router(collections.router)

    static = get_settings().static_dir
    index = static / "index.html"
    if index.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="spa-assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            """Serve a file of the built SPA, or `index.html` so the SPA's router takes the path."""
            file = static / path
            if path and file.is_file():
                return FileResponse(file)
            return FileResponse(index)

    return app


app = create_app()
