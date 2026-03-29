import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.auth import router as auth_router
from backend.api.routes.research import router as research_router
from backend.core.config import settings
from backend.db.qdrant_client import init_collection

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "loggers": {
        "verity": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
log = logging.getLogger("verity.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Verity starting up...")
    init_collection()
    log.info("Ready.")
    yield
    log.info("Verity shutting down.")


app = FastAPI(title="Verity", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(research_router)


@app.get("/health")
def health():
    return {"status": "ok"}
