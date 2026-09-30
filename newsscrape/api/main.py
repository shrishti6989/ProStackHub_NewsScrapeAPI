"""FastAPI app entrypoint for NewsScrape API."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from newsscrape.api import routes
from newsscrape.core.database import Database
from newsscrape.scheduler.jobs import start_scheduler, stop_scheduler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("Starting NewsScrape API ...")

    routes.state["db"] = Database("news.db")

    # Warm-up: if DB is empty, do a first scrape so /articles isn't empty
    if routes.state["db"].total_count() == 0:
        log.info("DB empty - running an initial scrape ...")
        try:
            routes.run_scrape()
        except Exception as exc:
            log.warning("Initial scrape failed: %s", exc)

    start_scheduler(routes.run_scrape)
    yield

    log.info("Shutting down NewsScrape API ...")
    stop_scheduler()
    if routes.state.get("db"):
        routes.state["db"].close()


app = FastAPI(
    title="NewsScrape API",
    description="Config-driven news scraper with deduplication and REST serving.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(routes.router)
