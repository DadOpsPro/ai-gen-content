import unittest

from pipeline.generator import strip_in_article_ai_disclosure
from pipeline.publisher import AI_DISCLOSURE


SENTENCE = (
    "Most of the content on this site is AI-generated. "
    "Chris reviews drafts before anything goes live."
)


class InArticleDisclosureTests(unittest.TestCase):
    def test_strips_standalone_markdown_paragraph(self):
        markdown = (
            "Opening paragraph about the bug.\n\n"
            f"{SENTENCE}\n\n"
            "## What to do\n\n"
            "Keep this section."
        )
        cleaned = strip_in_article_ai_disclosure(markdown)
        self.assertNotIn("AI-generated", cleaned)
        self.assertNotIn("goes live", cleaned)
        self.assertIn("Opening paragraph about the bug.", cleaned)
        self.assertIn("## What to do", cleaned)
        self.assertIn("Keep this section.", cleaned)

    def test_strips_html_paragraph(self):
        html = f"<p>Intro stays.</p>\n<p>{SENTENCE}</p>\n<p>Next stays.</p>"
        cleaned = strip_in_article_ai_disclosure(html)
        self.assertNotIn("goes live", cleaned)
        self.assertIn("<p>Intro stays.</p>", cleaned)
        self.assertIn("<p>Next stays.</p>", cleaned)

    def test_strips_split_html_paragraphs(self):
        html = (
            "<p>Most of the content on this site is AI-generated.</p>\n"
            "<p>Chris reviews drafts before anything goes live.</p>\n"
            "<p>Body stays.</p>"
        )
        cleaned = strip_in_article_ai_disclosure(html)
        self.assertNotIn("goes live", cleaned)
        self.assertIn("<p>Body stays.</p>", cleaned)

    def test_keeps_site_footer_disclosure(self):
        page = f"<p class=\"ai-disclosure\">{AI_DISCLOSURE}</p>"
        self.assertEqual(strip_in_article_ai_disclosure(page), page)
        self.assertIn("AI-drafted", strip_in_article_ai_disclosure(page))

    def test_keeps_unrelated_ai_generated_wording(self):
        text = "AI-generated tests missed the XSS sink. Chris reviews code before merge."
        self.assertEqual(strip_in_article_ai_disclosure(text), text)


if __name__ == "__main__":
    unittest.main()
