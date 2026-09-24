"""App factory. The built SPA (if present) is served for every non-API path."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kms.api import health
from kms.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="KMS", version="0.1.0")
    app.include_router(health.router)

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
