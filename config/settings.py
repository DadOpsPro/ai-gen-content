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
SITE_TAGLINE = "Hands-on notes on Java, GitLab AppSec, and developer-as-security-champion work"
SITE_URL = "https://aidevdefense.com"
AUTHOR_NAME = "Chris"

# Site-wide disclosure — keep short and honest.
AI_DISCLOSURE = (
    "Most articles on AI Dev Defense are AI-drafted and then reviewed before publish."
)

# Listing window: older posts leave home/archive but keep live permalinks.
LISTING_WINDOW_MONTHS = 12
HOME_RECENT_COUNT = 3

# Topic clusters biased to Chris's regular stack so he can add firsthand
# feedback. Deprioritize generic AI industry roundups / vendor news dumps.
TOPIC_CLUSTERS = [
    "Java 8 modernization security and testing",
    "legacy Java SAST and unit test gaps",
    "GitLab SAST to Jira ticket automation",
    "developer as security champion dual role",
    "Claude Security Mythos class code scans",
    "plain English CVE explainers for Java and GitLab stacks",
    "package registry and CI/CD supply chain for Maven and GitLab",
    "GitLab CI security pipeline with Jira",
    "Java application security testing in legacy services",
    "security champion practices in the SDLC",
    "Using Claude Code for application security",
    "Using Claude Code to simplify local development",
    "Security testing in GitLab CI/CD pipelines"
]

# ── API KEYS (load from environment variables) ─────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")      # optional: featured hero images
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
    "how_to_guide",      # Hands-on: GitLab SAST, Java tests, Jira automation
    "deep_dive",         # Practitioner write-ups Chris can annotate
    "tool_review",       # Tools on his stack only (GitLab, Jira, Claude Security)
    "comparison",        # Stack-adjacent comparisons, not vendor bake-offs
    "case_study",        # Dual-role / modernization stories
    "trend_roundup",     # Used sparingly — not generic AI industry dumps
]

# Output directory for generated static site
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "output")

# ── SEO ────────────────────────────────────────────────────────────────────────
SEO_FOCUS_KEYWORDS = [
    "GitLab SAST Jira automation",
    "Java 8 modernization security testing",
    "developer security champion",
    "Claude Security Mythos scans",
    "CVE explainer Java GitLab",
    "CI/CD package registry supply chain",
]
