"""App factory. The built SPA (if present) is served for every non-API path."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kms.api import assets, collections, health
from kms.config import get_settings


def flatten_validation_error(
    request: Request, validation_error: RequestValidationError
) -> JSONResponse:
    """FastAPI reports invalid input as a list of error objects; the API promises one string."""
    messages = []
    for error in validation_error.errors():
        # The location ends with the parameter's name, e.g. ("query", "collection").
        field = error["loc"][-1]
        messages.append(f"{field}: {error['msg']}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


def create_app() -> FastAPI:
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
            file = static / path
            if path and file.is_file():
                return FileResponse(file)
            return FileResponse(index)

    return app


app = create_app()
