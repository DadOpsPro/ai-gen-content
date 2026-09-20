import tempfile
import unittest
from pathlib import Path

from pipeline.publisher import StaticSiteGenerator


class PublisherListingTests(unittest.TestCase):
    def test_home_is_featured_plus_recent_not_a_dump(self):
        registry = [
            {
                "slug": "newest",
                "title": "Newest Dual Role Guide",
                "excerpt": "Pitch for the featured week.",
                "category": "AppSec",
                "tags": ["java"],
                "word_count": 400,
                "published_at": "2026-09-04T00:00:00Z",
            },
            {
                "slug": "second",
                "title": "GitLab SAST to Jira",
                "excerpt": "Recent card two.",
                "category": "DevSecOps",
                "tags": ["gitlab"],
                "word_count": 400,
                "published_at": "2026-09-03T00:00:00Z",
            },
            {
                "slug": "third",
                "title": "Mythos scans",
                "excerpt": "Recent card three.",
                "category": "AI Security",
                "tags": ["mythos"],
                "word_count": 400,
                "published_at": "2026-09-02T00:00:00Z",
            },
            {
                "slug": "fourth",
                "title": "Package registry",
                "excerpt": "Recent card four.",
                "category": "Supply chain",
                "tags": ["maven"],
                "word_count": 400,
                "published_at": "2026-09-01T00:00:00Z",
            },
            {
                "slug": "ancient",
                "title": "Should not list",
                "excerpt": "Soft retired.",
                "category": "News",
                "tags": [],
                "word_count": 400,
                "published_at": "2024-01-01T00:00:00Z",
            },
            {
                "slug": "spacex-cursor-acquisition-ai-coding",
                "title": "SpaceX Cursor Acquisition",
                "excerpt": "Trend post denylisted from listings.",
                "category": "News",
                "tags": [],
                "word_count": 2200,
                "published_at": "2026-09-03T12:00:00Z",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            gen = StaticSiteGenerator(tmp)
            gen._registry = registry
            gen.build_index()
            home = Path(tmp, "index.html").read_text(encoding="utf-8")
            archive = Path(tmp, "archive.html").read_text(encoding="utf-8")
            sitemap = Path(tmp, "sitemap.xml").read_text(encoding="utf-8")

        self.assertIn("Article of the Week", home)
        self.assertIn("Newest Dual Role Guide", home)
        self.assertIn("GitLab SAST to Jira", home)
        self.assertNotIn("Should not list", home)
        self.assertNotIn("SpaceX Cursor Acquisition", home)
        self.assertEqual(home.count('class="recent-card"'), 3)
        self.assertEqual(home.count('class="recent-card-link"'), 3)
        self.assertIn("quietly retired", archive)
        self.assertIn("thinner posts", archive)
        self.assertNotIn("Should not list", archive)
        self.assertNotIn("SpaceX Cursor Acquisition", archive)
        self.assertIn("spacex-cursor-acquisition-ai-coding.html", sitemap)
        self.assertIn("newest.html", sitemap)
        self.assertIn("AI-drafted", home)
        self.assertIn("/archive.html", home)
        self.assertIn('<div class="featured-panel" aria-hidden="true"></div>', home)
        self.assertNotIn("images/featured/", home)
