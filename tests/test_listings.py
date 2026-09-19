import unittest
from datetime import datetime, timezone

from pipeline.listings import (
    archive_by_month,
    featured_and_recent,
    is_in_listing_window,
    listed_articles,
    parse_published_at,
)


NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def rec(slug, published_at, title=None):
    return {
        "slug": slug,
        "title": title or slug,
        "excerpt": f"Pitch for {slug}",
        "category": "AppSec",
        "word_count": 400,
        "published_at": published_at,
    }


class ListingTests(unittest.TestCase):
    def test_parse_zulu_timestamp(self):
        dt = parse_published_at("2026-09-04T12:00:00.000Z")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_soft_retire_hides_old_posts(self):
        fresh = rec("new", "2026-08-01T00:00:00Z")
        old = rec("old", "2025-01-01T00:00:00Z")
        self.assertTrue(is_in_listing_window(fresh, now=NOW))
        self.assertFalse(is_in_listing_window(old, now=NOW))

    def test_missing_date_stays_listed(self):
        undated = rec("undated", None)
        self.assertTrue(is_in_listing_window(undated, now=NOW))

    def test_featured_and_recent_does_not_dump_all(self):
        registry = [
            rec("a", "2026-09-04T00:00:00Z", "Newest"),
            rec("b", "2026-09-03T00:00:00Z", "Two"),
            rec("c", "2026-09-02T00:00:00Z", "Three"),
            rec("d", "2026-09-01T00:00:00Z", "Four"),
            rec("retired", "2024-01-01T00:00:00Z", "Retired"),
        ]
        featured, recent = featured_and_recent(registry, now=NOW, recent_count=3)
        self.assertEqual(featured["slug"], "a")
        self.assertEqual([r["slug"] for r in recent], ["b", "c", "d"])
        self.assertNotIn("retired", [featured["slug"]] + [r["slug"] for r in recent])

    def test_archive_groups_by_month_and_excludes_retired(self):
        registry = [
            rec("sep", "2026-09-04T00:00:00Z"),
            rec("aug", "2026-08-16T00:00:00Z"),
            rec("old", "2025-01-01T00:00:00Z"),
        ]
        groups = archive_by_month(registry, now=NOW)
        labels = [label for label, _ in groups]
        self.assertEqual(labels, ["September 2026", "August 2026"])
        slugs = [article["slug"] for _, articles in groups for article in articles]
        self.assertNotIn("old", slugs)

    def test_listed_articles_reverse_chron(self):
        registry = [
            rec("older", "2026-06-07T00:00:00Z"),
            rec("newer", "2026-09-04T00:00:00Z"),
        ]
        listed = listed_articles(registry, now=NOW)
        self.assertEqual([r["slug"] for r in listed], ["newer", "older"])


if __name__ == "__main__":
    unittest.main()
