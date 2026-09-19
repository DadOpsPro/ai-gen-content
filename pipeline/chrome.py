"""
pipeline/chrome.py
──────────────────
Shared header, footer, and listing CSS for the static site.
Navy + teal, clean SaaS-blog — not flashy.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import AI_DISCLOSURE, SITE_NAME

NAV_ITEMS = (
    ("/", "Home"),
    ("/archive.html", "Archive"),
    ("/about.html", "About"),
)


def site_nav_html(active: str = "") -> str:
    links = []
    for href, label in NAV_ITEMS:
        css = ' class="active"' if active.lower() == label.lower() else ""
        links.append(f'<a href="{href}"{css}>{label}</a>')
    return f"""  <header class="site-header">
    <a href="/" class="logo">{SITE_NAME}</a>
    <nav>
      {" ".join(links)}
    </nav>
  </header>"""


def site_footer_html() -> str:
    year = datetime.now().year
    return f"""  <footer class="site-footer">
    <p class="ai-disclosure">{AI_DISCLOSURE}</p>
    <p>&copy; {year} {SITE_NAME} &middot;
    <a href="/archive.html">Archive</a> &middot;
    <a href="/about.html">About</a> &middot;
    <a href="/privacy.html">Privacy</a> &middot;
    <a href="/affiliate-disclosure.html">Affiliate Disclosure</a></p>
  </footer>"""


# Shared listing / chrome styles. Doubled braces so callers can .format() if needed.
SITE_CHROME_CSS = """
    :root {
      --navy: #0a0f1e;
      --navy-deep: #070b16;
      --teal: #00c896;
      --teal-dark: #00a67d;
      --text: #1a1a2e;
      --muted: #666;
      --card: #ffffff;
      --page: #f4f6f8;
      --line: #e6e9ee;
      --font: Georgia, 'Times New Roman', serif;
      --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font); color: var(--text); background: var(--page);
           line-height: 1.65; }
    a { color: var(--teal-dark); }
    .site-header { background: var(--navy); color: #fff; padding: 1rem 2rem;
                   display: flex; align-items: center; gap: 1rem; }
    .site-header a.logo { color: var(--teal); text-decoration: none;
                          font-weight: bold; font-size: 1.15rem; }
    .site-header nav { margin-left: auto; display: flex; gap: 1.5rem; }
    .site-header nav a { color: #aab; text-decoration: none; font-size: 0.9rem;
                         font-family: var(--sans); }
    .site-header nav a:hover, .site-header nav a.active { color: #fff; }
    .site-footer { background: var(--navy); color: #889; text-align: center;
                   padding: 2rem 1.5rem; margin-top: 4rem; font-size: 0.85rem;
                   font-family: var(--sans); }
    .site-footer a { color: #889; }
    .site-footer a:hover { color: #ccc; }
    .ai-disclosure { color: #9aa3ad; max-width: 640px; margin: 0 auto 0.85rem;
                     font-size: 0.82rem; line-height: 1.5; }
"""
