from fastapi import FastAPI

from app.config import settings
from app.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(router)
    return app


app = create_app()

