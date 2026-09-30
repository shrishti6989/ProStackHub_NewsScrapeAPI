"""Data models for NewsScrape API."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class Article:
    """A single scraped news article."""
    title: str
    url: str
    source: str
    author: Optional[str] = None
    published_at: Optional[str] = None       # ISO-8601 string
    summary: Optional[str] = None
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    id: Optional[int] = None                 # set after DB insert

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> "Article":
        """Build an Article from a sqlite3.Row."""
        return cls(
            id=row["id"],
            title=row["title"],
            url=row["url"],
            source=row["source"],
            author=row["author"],
            published_at=row["published_at"],
            summary=row["summary"],
            scraped_at=row["scraped_at"],
        )
