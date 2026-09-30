"""SQLite persistence for scraped articles with URL-based deduplication."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from newsscrape.core.models import Article


DEFAULT_DB_PATH = Path("news.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT NOT NULL,
    author       TEXT,
    published_at TEXT,
    summary      TEXT,
    scraped_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_source   ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_scraped  ON articles(scraped_at);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
"""


class Database:
    """Thin wrapper around sqlite3 for the NewsScrape API."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ---------- write ----------
    def insert_article(self, article: Article) -> bool:
        """Insert an article. Returns True if inserted, False if URL already exists."""
        try:
            self._conn.execute(
                """
                INSERT INTO articles
                    (title, url, source, author, published_at, summary, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.title,
                    article.url,
                    article.source,
                    article.author,
                    article.published_at,
                    article.summary,
                    article.scraped_at,
                ),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            # URL already exists — deduplication working as intended
            return False

    def insert_many(self, articles: List[Article]) -> Tuple[int, int]:
        """Insert many. Returns (inserted, skipped)."""
        inserted = skipped = 0
        for a in articles:
            if self.insert_article(a):
                inserted += 1
            else:
                skipped += 1
        return inserted, skipped

    # ---------- read ----------
    def get_by_url(self, url: str) -> Optional[Article]:
        row = self._conn.execute(
            "SELECT * FROM articles WHERE url = ?", (url,)
        ).fetchone()
        return Article.from_row(row) if row else None

    def list_articles(
        self,
        source: Optional[str] = None,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str = "scraped_at",
        order: str = "desc",
    ) -> Tuple[List[Article], int]:
        """Return (articles, total_count) applying filters."""
        where: List[str] = []
        params: List[Any] = []

        if source:
            where.append("source = ?")
            params.append(source)
        if search:
            where.append("(title LIKE ? OR summary LIKE ? OR author LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        if date_from:
            where.append("scraped_at >= ?")
            params.append(date_from)
        if date_to:
            where.append("scraped_at <= ?")
            params.append(date_to)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        order = "DESC" if order.lower() == "desc" else "ASC"
        allowed_order_cols = {"scraped_at", "published_at", "title", "source"}
        col = order_by if order_by in allowed_order_cols else "scraped_at"

        # total count (without pagination)
        total = self._conn.execute(
            f"SELECT COUNT(*) AS c FROM articles {where_sql}", params
        ).fetchone()["c"]

        # paginated rows
        rows = self._conn.execute(
            f"""
            SELECT * FROM articles {where_sql}
            ORDER BY {col} {order}
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
        return [Article.from_row(r) for r in rows], total

    def count_by_source(self) -> Dict[str, int]:
        rows = self._conn.execute(
            "SELECT source, COUNT(*) AS c FROM articles GROUP BY source"
        ).fetchall()
        return {r["source"]: r["c"] for r in rows}

    def total_count(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) AS c FROM articles"
        ).fetchone()["c"]

    def close(self) -> None:
        self._conn.close()
