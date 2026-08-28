"""
Content Engine Configuration
Edit this file to customize your niche, APIs, and monetization settings.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict

# ── NICHE CONFIGURATION ────────────────────────────────────────────────────────
NICHE = "AI in Software Testing and Security"
SITE_NAME = "AI Dev Defense"
SITE_TAGLINE = "AI-powered insights for software testing & application security"
SITE_URL = "https://aidevdefense.com"
AUTHOR_NAME = "Chris"

# Topic clusters for content generation (mix evergreen + trending)
TOPIC_CLUSTERS = [
    "AI test automation tools",
    "LLM testing strategies",
    "synthetic test data generation",
    "AI-driven bug detection",
    "visual regression testing AI",
    "self-healing test frameworks",
    "AI code review tools",
    "flaky test elimination with AI",
    "performance testing automation",
    "security testing AI tools",
]

# ── API KEYS (load from environment variables) ─────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SERPER_API_KEY    = os.getenv("SERPER_API_KEY", "")      # Google Search API (serper.dev)
WORDPRESS_URL     = os.getenv("WORDPRESS_URL", "")
WORDPRESS_USER    = os.getenv("WORDPRESS_USER", "")
WORDPRESS_APP_PW  = os.getenv("WORDPRESS_APP_PW", "")   # WP Application Password
MAILCHIMP_API_KEY = os.getenv("MAILCHIMP_API_KEY", "")
MAILCHIMP_LIST_ID = os.getenv("MAILCHIMP_LIST_ID", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")

# ── MONETIZATION ───────────────────────────────────────────────────────────────
ADSENSE_PUBLISHER_ID = os.getenv("ADSENSE_PUB_ID", "pub-XXXXXXXXXXXXXXXX")
ADSENSE_SLOT_ID      = os.getenv("ADSENSE_SLOT_ID", "XXXXXXXXXX")

# Amazon Associates
AMAZON_TAG = os.getenv("AMAZON_TAG", "yourtag-20")

# Affiliate link mapping: keyword → affiliate URL
AFFILIATE_LINKS: Dict[str, str] = {
    "Playwright":       f"https://amazon.com/s?k=playwright+testing&tag={AMAZON_TAG}",
    "Cypress":          "https://cypress.io?ref=testaiweekly",
    "Testim":           "https://testim.io?ref=testaiweekly",
    "mabl":             "https://mabl.com?ref=testaiweekly",
    "Applitools":       "https://applitools.com?ref=testaiweekly",
    "Diffblue":         "https://diffblue.com?ref=testaiweekly",
    "GitHub Copilot":   "https://github.com/features/copilot?ref=testaiweekly",
    "Cursor":           "https://cursor.sh?ref=testaiweekly",
    "Postman":          "https://postman.com?ref=testaiweekly",
    "k6":               "https://k6.io?ref=testaiweekly",
}

# Premium report pricing (Stripe)
PREMIUM_REPORT_PRICE_USD = 29  # dollars

# ── CONTENT SETTINGS ───────────────────────────────────────────────────────────
ARTICLES_PER_SEED_RUN = 15        # Initial SEO seed batch
NEWSLETTER_FREQUENCY  = "weekly"  # weekly | biweekly | monthly
MIN_WORD_COUNT        = 400
MAX_WORD_COUNT        = 750
ARTICLE_TYPES = [
    "tool_review",       # "Top 5 AI testing tools for X"
    "how_to_guide",      # "How to use AI to generate test cases"
    "trend_roundup",     # "This week in AI testing"
    "comparison",        # "Playwright vs Cypress: AI features compared"
    "case_study",        # "How X company reduced test flakiness by 80%"
    "deep_dive",         # "Complete guide to LLM testing"
]

# Output directory for generated static site
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "output")

# ── SEO ────────────────────────────────────────────────────────────────────────
SEO_FOCUS_KEYWORDS = [
    "AI testing tools 2025",
    "automated software testing AI",
    "AI test generation",
    "LLM testing best practices",
    "AI QA automation",
]
