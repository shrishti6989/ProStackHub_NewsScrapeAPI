"""Config-driven news scraper using requests + BeautifulSoup."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from newsscrape.config.loader import Config, SourceConfig
from newsscrape.core.models import Article


log = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """Outcome of scraping one source."""
    source: str
    success: bool
    articles: List[Article] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class ScrapeReport:
    """Overall outcome of a scrape run."""
    results: List[SourceResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    @property
    def total_articles(self) -> int:
        return sum(len(r.articles) for r in self.results)

    @property
    def successful_sources(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed_sources(self) -> int:
        return sum(1 for r in self.results if not r.success)


class Scraper:
    """Scrapes all sources defined in the Config."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.defaults.get(
                "user_agent",
                "NewsScrapeBot/1.0 (+https://github.com/shrishti6989)",
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        })

    # ---------- HTTP ----------
    def fetch(self, url: str, timeout: int = 15, retries: int = 2) -> Optional[str]:
        """GET a URL with retry on transient failures."""
        for attempt in range(retries + 1):
            try:
                r = self.session.get(url, timeout=timeout)
                if r.status_code == 200:
                    return r.text
                log.warning("HTTP %s for %s (attempt %d)", r.status_code, url, attempt + 1)
            except requests.RequestException as exc:
                log.warning("Request failed for %s: %s (attempt %d)", url, exc, attempt + 1)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
        return None

    # ---------- extraction ----------
    def scrape_source(self, source: SourceConfig) -> SourceResult:
        started = time.time()
        try:
            html = self.fetch(source.url, timeout=source.timeout_seconds)
            if html is None:
                return SourceResult(
                    source=source.name,
                    success=False,
                    error="Fetch failed after retries",
                    duration_seconds=time.time() - started,
                )

            head = html[:500].lower()
            if "<rss" in head or "<feed" in head or "<?xml" in head:
                parser = "xml"
            else:
                parser = "lxml"
            soup = BeautifulSoup(html, parser)

            items = soup.select(source.item_selector)
            if not items:
                return SourceResult(
                    source=source.name,
                    success=False,
                    error=f"No items matched selector '{source.item_selector}'",
                    duration_seconds=time.time() - started,
                )

            articles: List[Article] = []
            for item in items[: source.max_articles_per_source]:
                article = self._extract_item(item, source)
                if article:
                    articles.append(article)

            if not articles:
                return SourceResult(
                    source=source.name,
                    success=False,
                    error=f"Matched {len(items)} items but extracted 0 articles",
                    duration_seconds=time.time() - started,
                )

            return SourceResult(
                source=source.name,
                success=True,
                articles=articles,
                duration_seconds=time.time() - started,
            )

        except Exception as exc:
            log.exception("Unexpected error scraping %s", source.name)
            return SourceResult(
                source=source.name,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_seconds=time.time() - started,
            )

    def _extract_item(self, item: Any, source: SourceConfig) -> Optional[Article]:
        """Extract one article from an item element."""
        title_el = item.select_one(source.title_selector) if source.title_selector else None
        link_el = item.select_one(source.link_selector) if source.link_selector else None

        if not title_el or not link_el:
            return None

        title = self._clean_text(title_el.get_text())
        # RSS <link> sometimes has text, sometimes href attr
        href = link_el.get("href") or link_el.get_text()
        href = (href or "").strip()
        if not title or not href:
            return None

        url = self._normalize_url(href, source.base_url or source.url)
        if not url:
            return None

        author = None
        if source.author_selector:
            el = item.select_one(source.author_selector)
            if el:
                author = self._clean_text(el.get_text())

        published_at = None
        if source.date_selector:
            el = item.select_one(source.date_selector)
            if el:
                raw = el.get("datetime") or el.get_text()
                published_at = self._normalize_date(self._clean_text(raw))

        summary = None
        if source.summary_selector:
            el = item.select_one(source.summary_selector)
            if el:
                summary = self._clean_text(el.get_text())[:500]

        return Article(
            title=title,
            url=url,
            source=source.name,
            author=author,
            published_at=published_at,
            summary=summary,
        )

    # ---------- helpers ----------
    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split()).strip()

    @staticmethod
    def _normalize_url(href: str, base: str) -> Optional[str]:
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            return None
        full = urljoin(base, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            return None
        return parsed._replace(fragment="").geturl()

    @staticmethod
    def _normalize_date(raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        raw = raw.strip()
        if not raw:
            return None
        return raw

    # ---------- run all ----------
    def scrape_all(self) -> ScrapeReport:
        """Scrape all configured sources with rate limiting between them."""
        rate = float(self.config.defaults.get("rate_limit_seconds", 1.0))
        report = ScrapeReport()
        report.started_at = datetime.now(timezone.utc).isoformat()

        for i, src in enumerate(self.config.sources):
            if i > 0:
                time.sleep(rate)
            log.info("Scraping %s ...", src.name)
            report.results.append(self.scrape_source(src))

        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report
