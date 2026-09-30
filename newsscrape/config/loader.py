"""YAML config loader for NewsScrape API."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent / "sources.yaml"


@dataclass
class SourceConfig:
    """Configuration for a single news source."""
    name: str
    url: str
    item_selector: str
    title_selector: str
    link_selector: str
    base_url: str = ""
    author_selector: Optional[str] = None
    date_selector: Optional[str] = None
    summary_selector: Optional[str] = None

    # Fill defaults from the "defaults" section
    rate_limit_seconds: float = 1.0
    timeout_seconds: int = 15
    max_articles_per_source: int = 20
    user_agent: str = "NewsScrapeBot/1.0"


@dataclass
class Config:
    sources: List[SourceConfig]
    defaults: Dict[str, Any]


REQUIRED_FIELDS = {"name", "url", "item_selector", "title_selector", "link_selector"}


def load_config(path: str | Path | None = None) -> Config:
    """Load the YAML config and validate it."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    defaults = raw.get("defaults", {}) or {}
    raw_sources = raw.get("sources", []) or []

    sources: List[SourceConfig] = []
    for i, entry in enumerate(raw_sources):
        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            raise ValueError(
                f"Source #{i} ({entry.get('name', '?')}) missing required fields: {missing}"
            )
        merged = {**defaults, **entry}
        sources.append(SourceConfig(**{
            k: merged[k] for k in SourceConfig.__dataclass_fields__
            if k in merged
        }))

    return Config(sources=sources, defaults=defaults)
