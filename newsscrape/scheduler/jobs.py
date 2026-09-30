"""APScheduler setup - auto-scrape every 6 hours with run logging."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


log = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

# global run history (in-memory; also persisted by the caller via DB)
run_log: Dict[str, Any] = {
    "runs_total": 0,
    "runs_failed": 0,
    "last_run_at": None,
    "last_run_success": None,
    "last_error": None,
    "next_run_at": None,
}

SCRAPE_INTERVAL_HOURS = 6


def _run_job(scrape_fn: Callable[[], Dict[str, Any]]) -> None:
    """Wrapper around the scrape function that logs results."""
    started = datetime.now(timezone.utc)
    log.info("[scheduler] Scrape job starting at %s", started.isoformat())
    try:
        summary = scrape_fn() or {}
        run_log["runs_total"] += 1
        run_log["last_run_at"] = started.isoformat()
        run_log["last_run_success"] = True
        run_log["last_error"] = None

        log.info(
            "[scheduler] Scrape OK - inserted=%s skipped=%s sources_ok=%s/%s",
            summary.get("inserted"),
            summary.get("skipped_duplicates"),
            summary.get("successful_sources"),
            summary.get("successful_sources", 0) + summary.get("failed_sources", 0),
        )
    except Exception as exc:
        run_log["runs_total"] += 1
        run_log["runs_failed"] += 1
        run_log["last_run_at"] = started.isoformat()
        run_log["last_run_success"] = False
        run_log["last_error"] = f"{type(exc).__name__}: {exc}"
        log.exception("[scheduler] Scrape job FAILED")

    if _scheduler is not None:
        job = _scheduler.get_job("news_scrape")
        if job and job.next_run_time:
            run_log["next_run_at"] = job.next_run_time.isoformat()


def start_scheduler(scrape_fn: Callable[[], Dict[str, Any]]) -> None:
    """Start the background scheduler. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        func=_run_job,
        args=[scrape_fn],
        trigger=IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS),
        id="news_scrape",
        name="Scrape all news sources every 6 hours",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()

    job = _scheduler.get_job("news_scrape")
    if job and job.next_run_time:
        run_log["next_run_at"] = job.next_run_time.isoformat()

    log.info(
        "[scheduler] Started - will scrape every %s hours. Next run: %s",
        SCRAPE_INTERVAL_HOURS,
        run_log["next_run_at"],
    )


def stop_scheduler() -> None:
    """Stop the scheduler if running."""
    global _scheduler
    if _scheduler is not None:
        log.info("[scheduler] Stopping ...")
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_run_log() -> Dict[str, Any]:
    """Expose scheduler status (used by /health)."""
    return dict(run_log)
