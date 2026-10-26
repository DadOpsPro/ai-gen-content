import json
import tempfile
import unittest
from pathlib import Path

from pipeline import publisher
from pipeline.publisher import StaticSiteGenerator, add_robots_noindex


class NoindexOrphanPostsTest(unittest.TestCase):
    def test_add_robots_noindex_is_idempotent(self):
        html = '<html><head>\n<meta charset="UTF-8">\n<title>x</title></head></html>'
        once = add_robots_noindex(html)
        self.assertIn('<meta name="robots" content="noindex">', once)
        self.assertEqual(add_robots_noindex(once), once)

    def test_only_listed_orphans_get_noindex(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp, "noindex.json")
            cfg.write_text(json.dumps({"slugs": ["orphan", "registered"]}), encoding="utf-8")
            gen = StaticSiteGenerator(str(Path(tmp, "out")))
            gen._registry = [{"slug": "registered"}]
            gen.posts_dir.mkdir(parents=True, exist_ok=True)
            page = '<html><head><meta charset="UTF-8"></head><body></body></html>'
            for slug in ("orphan", "registered", "other"):
                Path(gen.posts_dir, f"{slug}.html").write_text(page, encoding="utf-8")
            old = publisher.NOINDEX_POSTS_PATH
            publisher.NOINDEX_POSTS_PATH = cfg
            try:
                self.assertEqual(gen.apply_noindex_to_orphan_posts(), 1)
            finally:
                publisher.NOINDEX_POSTS_PATH = old
            read = lambda s: Path(gen.posts_dir, f"{s}.html").read_text(encoding="utf-8")
            self.assertIn('name="robots"', read("orphan"))
            self.assertNotIn('name="robots"', read("registered"))
            self.assertNotIn('name="robots"', read("other"))

    def test_config_never_lists_registered_key_posts(self):
        slugs = publisher.load_noindex_slugs()
        for key in (
            "insecure-deserialization-plain-english",
            "xss-plain-english-cve-type-still-ships",
            "replace-java-8-spring-boot-angular-strangler",
            "sql-injection-plain-english-user-input",
        ):
            self.assertNotIn(key, slugs)


if __name__ == "__main__":
    unittest.main()
