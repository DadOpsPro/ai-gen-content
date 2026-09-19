import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.featured_image import (
    IMAGE_DIR,
    build_featured_image_prompt,
    ensure_featured_image,
    featured_image_alt,
    find_cached_featured_image,
)
from pipeline.publisher import StaticSiteGenerator


RECORD = {
    "slug": "newest",
    "title": "Newest Dual Role Guide",
    "excerpt": "Pitch for the featured week.",
    "category": "AppSec",
    "tags": ["java", "security champion"],
    "word_count": 400,
    "published_at": "2026-09-04T00:00:00Z",
}


class FeaturedImageTests(unittest.TestCase):
    def test_prompt_is_brand_locked_and_uses_article(self):
        prompt = build_featured_image_prompt(
            "Dev and Security Champ: Managing the Dual Role",
            "Getting appointed as a security champion while maintaining your "
            "dev duties is real.",
            ["dual role", "boundaries"],
        )
        self.assertIn("#0a0f1e", prompt)
        self.assertIn("#00c896", prompt)
        self.assertIn("Managing the Dual Role", prompt)
        self.assertIn("security champion", prompt)
        self.assertIn("dual role", prompt)
        self.assertIn("boundaries", prompt)
        self.assertIn("No photoreal faces", prompt)
        self.assertIn("no neon cyberpunk", prompt)
        self.assertIn("no vendor logos", prompt)
        self.assertIn("no typography", prompt)

    def test_alt_text_is_soft_ai_note(self):
        self.assertEqual(
            featured_image_alt("Newest Dual Role Guide"),
            "Editorial illustration for Newest Dual Role Guide (AI-generated)",
        )

    def test_cache_hit_skips_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            cached = Path(tmp, IMAGE_DIR)
            cached.mkdir(parents=True)
            (cached / "newest.webp").write_bytes(b"RIFF....WEBP")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
                with patch("pipeline.featured_image._generate_openai_image") as gen:
                    rel = ensure_featured_image(RECORD, Path(tmp))
            gen.assert_not_called()
            self.assertEqual(rel, f"{IMAGE_DIR}/newest.webp")

    def test_missing_key_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                rel = ensure_featured_image(RECORD, Path(tmp))
            self.assertIsNone(rel)
            self.assertFalse(list(Path(tmp, IMAGE_DIR).glob("*")))

    def test_generation_failure_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
                with patch(
                    "pipeline.featured_image._generate_openai_image",
                    side_effect=RuntimeError("api down"),
                ):
                    rel = ensure_featured_image(RECORD, Path(tmp))
            self.assertIsNone(rel)

    def test_static_seed_image_used_for_live_featured_slug(self):
        record = {
            "slug": "developer-security-champion-dual-role",
            "title": "Dev and Security Champ: Managing the Dual Role",
            "excerpt": "Getting appointed as a security champion.",
            "tags": ["security champion", "application security"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            rel = ensure_featured_image(record, Path(tmp))
            dest = Path(tmp, IMAGE_DIR, "developer-security-champion-dual-role.webp")
            self.assertEqual(
                rel, f"{IMAGE_DIR}/developer-security-champion-dual-role.webp"
            )
            self.assertTrue(dest.is_file())
            self.assertGreater(dest.stat().st_size, 0)

    def test_find_cached_prefers_webp(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp, IMAGE_DIR)
            folder.mkdir(parents=True)
            (folder / "newest.webp").write_bytes(b"webp")
            (folder / "newest.png").write_bytes(b"png")
            found = find_cached_featured_image("newest", Path(tmp))
            self.assertEqual(found.name, "newest.webp")


class FeaturedImagePublisherTests(unittest.TestCase):
    def test_home_renders_cached_featured_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            gen = StaticSiteGenerator(tmp)
            gen._registry = [RECORD]
            featured_dir = Path(tmp, IMAGE_DIR)
            featured_dir.mkdir(parents=True)
            (featured_dir / "newest.webp").write_bytes(b"RIFF....WEBP")
            with patch.object(gen, "restore_featured_images"):
                gen.build_index()
            home = Path(tmp, "index.html").read_text(encoding="utf-8")

        self.assertIn('src="images/featured/newest.webp"', home)
        self.assertIn(
            "Editorial illustration for Newest Dual Role Guide (AI-generated)",
            home,
        )
        self.assertNotIn(
            '<div class="featured-panel" aria-hidden="true"></div>', home
        )
        self.assertIn("object-fit: cover", home)


if __name__ == "__main__":
    unittest.main()
