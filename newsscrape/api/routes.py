"""FastAPI route definitions for NewsScrape API."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from newsscrape.config.loader import load_config
from newsscrape.core.database import Database
from newsscrape.core.scraper import Scraper


log = logging.getLogger(__name__)

router = APIRouter()

state: Dict[str, Any] = {
    "db": None,
    "last_scrape": None,
}


def get_db() -> Database:
    db = state.get("db")
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return db


def run_scrape() -> Dict[str, Any]:
    """Fetch all sources, insert into DB, return a summary."""
    cfg = load_config()
    scraper = Scraper(cfg)
    report = scraper.scrape_all()

    db = get_db()
    inserted = skipped = 0
    per_source: Dict[str, int] = {}

    for r in report.results:
        if not r.success:
            continue
        ins, skip = db.insert_many(r.articles)
        inserted += ins
        skipped += skip
        per_source[r.source] = ins

    summary = {
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "total_scraped": report.total_articles,
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "successful_sources": report.successful_sources,
        "failed_sources": report.failed_sources,
        "per_source_inserted": per_source,
        "errors": {r.source: r.error for r in report.results if not r.success},
    }
    state["last_scrape"] = summary
    return summary


@router.get("/")
def root() -> Dict[str, Any]:
    return {
        "name": "NewsScrape API",
        "version": "1.0.0",
        "endpoints": [
            "GET  /articles",
            "POST /scrape",
            "GET  /health",
            "GET  /docs",
        ],
    }


@router.get("/health")
def health() -> Dict[str, Any]:
    from newsscrape.scheduler.jobs import get_run_log
    db = get_db()
    cfg = load_config()
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "sources_configured": [s.name for s in cfg.sources],
        "total_articles": db.total_count(),
        "articles_by_source": db.count_by_source(),
        "last_scrape": state.get("last_scrape"),
        "scheduler": get_run_log(),
    }


@router.get("/articles")
def list_articles(
    source: Optional[str] = Query(None, description="Filter by source name"),
    search: Optional[str] = Query(None, description="Search title/summary/author"),
    date_from: Optional[str] = Query(None, description="ISO date lower bound"),
    date_to: Optional[str] = Query(None, description="ISO date upper bound"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_by: str = Query("scraped_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> Dict[str, Any]:
    db = get_db()
    rows, total = db.list_articles(
        source=source,
        search=search,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order=order,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "articles": [a.to_dict() for a in rows],
    }


@router.post("/scrape")
def trigger_scrape() -> Dict[str, Any]:
    """Manually trigger a scrape across all configured sources."""
    try:
        return run_scrape()
    except Exception as exc:
        log.exception("Manual scrape failed")
        raise HTTPException(status_code=500, detail=f"Scrape failed: {exc}")
