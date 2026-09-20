import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import MIN_IN_ARTICLE_AD_WORDS
from pipeline.publisher import (
    ARTICLE_TEMPLATE,
    cap_manual_ad_units,
    html_word_count,
    wrap_with_ads,
)


SHORT_BODY = """
<h2>First heading</h2>
<p>A short practitioner note with only a few hundred words of body copy.</p>
<h2>Second heading</h2>
<p>Still well under the in-article ad threshold.</p>
"""

LONG_PARAS = " ".join(["word"] * 500)


def long_body_two_headings():
    return (
        f"<h2>First heading</h2><p>{LONG_PARAS}</p>"
        f"<h2>Second heading</h2><p>{LONG_PARAS}</p>"
        f"<h2>Third heading</h2><p>{LONG_PARAS}</p>"
        f"<p>{LONG_PARAS}</p>"
    )


def long_body_no_headings():
    return f"<p>{' '.join(['word'] * 950)}</p>"


class AdInjectionTests(unittest.TestCase):
    def test_short_post_gets_no_in_article_unit(self):
        html = wrap_with_ads(SHORT_BODY, word_count=400)
        self.assertNotIn("adsbygoogle", html)
        self.assertNotIn('class="ad-unit"', html)
        self.assertIn("affiliate-notice", html)
        self.assertIn("First heading", html)

    def test_short_post_does_not_inject_after_first_h2(self):
        html = wrap_with_ads(SHORT_BODY, word_count=MIN_IN_ARTICLE_AD_WORDS - 1)
        first_h2 = html.lower().find("<h2>first heading</h2>")
        self.assertGreater(first_h2, -1)
        after_first = html[first_h2:]
        self.assertNotIn('class="ad-unit"', after_first)

    def test_long_post_caps_at_one_unit_after_second_heading(self):
        body = long_body_two_headings()
        self.assertGreaterEqual(html_word_count(body), MIN_IN_ARTICLE_AD_WORDS)
        html = wrap_with_ads(body, word_count=html_word_count(body))
        self.assertEqual(html.count('class="ad-unit"'), 1)
        self.assertEqual(html.count('class="adsbygoogle"'), 1)
        second = html.lower().find("<h2>second heading</h2>")
        third = html.lower().find("<h2>third heading</h2>")
        ad_at = html.find('class="ad-unit"')
        self.assertGreater(ad_at, second)
        self.assertLess(ad_at, third)

    def test_long_post_without_two_headings_gets_end_unit(self):
        body = long_body_no_headings()
        html = wrap_with_ads(body, word_count=950)
        self.assertEqual(html.count('class="ad-unit"'), 1)
        self.assertTrue(html.rstrip().endswith("</div>"))
        self.assertGreater(html.rfind('class="ad-unit"'), html.find("<p>"))

    def test_article_template_hides_unfilled_units_and_keeps_loader(self):
        self.assertIn('ins.adsbygoogle[data-ad-status="unfilled"]', ARTICLE_TEMPLATE)
        self.assertIn("pagead/js/adsbygoogle.js?client={adsense_pub}", ARTICLE_TEMPLATE)
        self.assertIn("ca-pub-9384256595608147", ARTICLE_TEMPLATE)

    def test_cap_removes_all_units_on_short_existing_html(self):
        page = (
            '<div class="article-content">'
            "<h2>Only heading</h2><p>Tiny body.</p>"
            '<div class="ad-unit"><ins class="adsbygoogle"></ins></div>'
            "</div>"
            '<div class="tags">Tags</div>'
        )
        capped = cap_manual_ad_units(page, word_count=40)
        self.assertNotIn('class="ad-unit"', capped)
        self.assertIn("Tiny body.", capped)

    def test_cap_keeps_single_end_unit_on_long_existing_html(self):
        early = '<div class="ad-unit" data-where="early"><ins class="adsbygoogle"></ins></div>'
        end = '<div class="ad-unit" data-where="end"><ins class="adsbygoogle"></ins></div>'
        page = (
            '<div class="article-content">'
            f"<h2>First</h2>{early}<p>{LONG_PARAS}</p>"
            f"<h2>Second</h2><p>{LONG_PARAS}</p>{end}"
            "</div>"
            '<div class="tags">Tags</div>'
        )
        capped = cap_manual_ad_units(page, word_count=1200)
        self.assertEqual(capped.count('class="ad-unit"'), 1)
        self.assertIn('data-where="end"', capped)
        self.assertNotIn('data-where="early"', capped)


class SanitizeRestoredPostsTests(unittest.TestCase):
    def test_build_index_caps_restored_post_ads(self):
        from pipeline.publisher import StaticSiteGenerator

        early = '<div class="ad-unit" data-where="early"><ins class="adsbygoogle"></ins></div>'
        end = '<div class="ad-unit" data-where="end"><ins class="adsbygoogle"></ins></div>'
        html = (
            "<html><body>"
            '<div class="article-content">'
            f"<h2>First</h2>{early}<p>{LONG_PARAS}</p>"
            f"<h2>Second</h2><p>{LONG_PARAS}</p>{end}"
            "</div>"
            '<div class="tags">Tags</div>'
            "</body></html>"
        )
        registry = [
            {
                "slug": "developer-security-champion-dual-role",
                "title": "Keep listed",
                "excerpt": "Keep",
                "category": "AppSec",
                "tags": [],
                "word_count": 1200,
                "published_at": "2026-09-04T00:00:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            gen = StaticSiteGenerator(tmp)
            gen._registry = registry
            post = Path(tmp, "posts", "developer-security-champion-dual-role.html")
            post.write_text(html, encoding="utf-8")
            with patch.object(gen, "restore_featured_images"):
                gen.build_index()
            written = post.read_text(encoding="utf-8")
        self.assertEqual(written.count('class="ad-unit"'), 1)
        self.assertIn('data-where="end"', written)
        self.assertNotIn('data-where="early"', written)
