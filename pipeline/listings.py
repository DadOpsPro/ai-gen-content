"""
pipeline/listings.py
────────────────────
Homepage / archive listing helpers.

Posts older than LISTING_WINDOW_MONTHS, or listed in
config/soft_retire.json, leave listings (home, archive, index) but keep
their permalinks and sitemap entries. No hard deletes.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import HOME_RECENT_COUNT, LISTING_WINDOW_MONTHS

ArticleRecord = Dict

SOFT_RETIRE_PATH = Path(__file__).resolve().parent.parent / "config" / "soft_retire.json"


def normalize_slug(slug: str) -> str:
    """Strip posts/ prefix and .html suffix so denylist entries match registry slugs."""
    text = (slug or "").strip()
    if text.startswith("posts/"):
        text = text[6:]
    if text.endswith(".html"):
        text = text[:-5]
    return text


@lru_cache(maxsize=1)
def load_soft_retired_slugs(path: Optional[str] = None) -> Set[str]:
    """Load the soft-retire denylist. Permalinks are not deleted."""
    retire_path = Path(path) if path else SOFT_RETIRE_PATH
    if not retire_path.exists():
        return set()
    try:
        data = json.loads(retire_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    raw = data.get("slugs", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return set()
    return {normalize_slug(str(slug)) for slug in raw if slug}


def is_soft_retired(
    record: ArticleRecord,
    retired_slugs: Optional[Iterable[str]] = None,
) -> bool:
    """True if the slug is on the human-listing denylist."""
    if retired_slugs is None:
        retired = load_soft_retired_slugs()
    else:
        retired = {normalize_slug(str(slug)) for slug in retired_slugs}
    return normalize_slug(str(record.get("slug") or "")) in retired


def parse_published_at(value: Optional[str]) -> Optional[datetime]:
    """Parse a registry published_at string into an aware UTC datetime."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def listing_cutoff(now: Optional[datetime] = None,
                   months: int = LISTING_WINDOW_MONTHS) -> datetime:
    """Approximate N-month cutoff (~30.44 days per month)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now - timedelta(days=int(months * 30.44))


def is_in_listing_window(record: ArticleRecord,
                         now: Optional[datetime] = None,
                         months: int = LISTING_WINDOW_MONTHS) -> bool:
    """
    True if the article should appear on home/archive.

    Missing dates stay listed so we never hide a live post we cannot date.
    """
    published = parse_published_at(record.get("published_at"))
    if published is None:
        return True
    return published >= listing_cutoff(now=now, months=months)


def _sort_key(record: ArticleRecord) -> datetime:
    published = parse_published_at(record.get("published_at"))
    if published is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return published


def listed_articles(
    registry: Iterable[ArticleRecord],
    now: Optional[datetime] = None,
    months: int = LISTING_WINDOW_MONTHS,
    retired_slugs: Optional[Iterable[str]] = None,
) -> List[ArticleRecord]:
    """Reverse-chron articles still inside the listing window and not denylisted."""
    if retired_slugs is None:
        retired = load_soft_retired_slugs()
    else:
        retired = {normalize_slug(str(slug)) for slug in retired_slugs}
    visible = [
        record for record in registry
        if is_in_listing_window(record, now=now, months=months)
        and normalize_slug(str(record.get("slug") or "")) not in retired
    ]
    return sorted(visible, key=_sort_key, reverse=True)


def featured_and_recent(
    registry: Iterable[ArticleRecord],
    now: Optional[datetime] = None,
    recent_count: int = HOME_RECENT_COUNT,
    retired_slugs: Optional[Iterable[str]] = None,
) -> Tuple[Optional[ArticleRecord], List[ArticleRecord]]:
    """Newest listed post as Article of the Week, then up to N recent cards."""
    visible = listed_articles(registry, now=now, retired_slugs=retired_slugs)
    if not visible:
        return None, []
    featured = visible[0]
    recent = visible[1:1 + recent_count]
    return featured, recent


def archive_by_month(
    registry: Iterable[ArticleRecord],
    now: Optional[datetime] = None,
    retired_slugs: Optional[Iterable[str]] = None,
) -> List[Tuple[str, List[ArticleRecord]]]:
    """
    Group listed articles by calendar month, newest month first.

    Returns a list of (label, articles) such as ("September 2026", [...]).
    """
    groups: "OrderedDict[str, List[ArticleRecord]]" = OrderedDict()
    for record in listed_articles(registry, now=now, retired_slugs=retired_slugs):
        published = parse_published_at(record.get("published_at"))
        if published is None:
            label = "Undated"
        else:
            label = published.strftime("%B %Y")
        groups.setdefault(label, []).append(record)
    return list(groups.items())


def read_time_minutes(record: ArticleRecord) -> int:
    word_count = int(record.get("word_count") or 0)
    return max(1, word_count // 200)
