"""
pipeline/publisher.py
─────────────────────
Publishes generated articles to:
  1. WordPress (via REST API + Application Passwords)
  2. Static HTML site (auto-generated)
  3. Mailchimp newsletter
"""

import httpx
import json
import os
import sys
from base64 import b64encode
from datetime import datetime
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import (
    WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PW,
    MAILCHIMP_API_KEY, MAILCHIMP_LIST_ID,
    SITE_NAME, SITE_URL, ADSENSE_PUBLISHER_ID, ADSENSE_SLOT_ID,
    OUTPUT_DIR
)
from pipeline.generator import GeneratedArticle


# ── WORDPRESS PUBLISHER ────────────────────────────────────────────────────────

class WordPressPublisher:
    def __init__(self):
        self.base_url = WORDPRESS_URL.rstrip("/") + "/wp-json/wp/v2"
        token = b64encode(f"{WORDPRESS_USER}:{WORDPRESS_APP_PW}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def get_or_create_tag(self, tag_name: str) -> Optional[int]:
        """Get existing tag ID or create new tag."""
        try:
            r = httpx.get(
                f"{self.base_url}/tags",
                headers=self.headers,
                params={"search": tag_name}
            )
            tags = r.json()
            if tags:
                return tags[0]["id"]
            # Create new tag
            r = httpx.post(
                f"{self.base_url}/tags",
                headers=self.headers,
                json={"name": tag_name}
            )
            return r.json().get("id")
        except Exception:
            return None

    def get_or_create_category(self, category_name: str) -> Optional[int]:
        """Get existing category ID or create new category."""
        try:
            r = httpx.get(
                f"{self.base_url}/categories",
                headers=self.headers,
                params={"search": category_name}
            )
            cats = r.json()
            if cats:
                return cats[0]["id"]
            r = httpx.post(
                f"{self.base_url}/categories",
                headers=self.headers,
                json={"name": category_name}
            )
            return r.json().get("id")
        except Exception:
            return None

    def publish(self, article: GeneratedArticle, status: str = "publish") -> dict:
        """Publish an article to WordPress."""
        if not WORDPRESS_URL:
            print("  [SKIP] WordPress not configured")
            return {}

        # Wrap content with AdSense + affiliate disclaimer
        full_content = wrap_with_ads(article.content_html)

        # Resolve tag/category IDs
        tag_ids = [self.get_or_create_tag(t) for t in article.tags[:5]]
        tag_ids = [t for t in tag_ids if t]
        cat_id = self.get_or_create_category(article.category)

        payload = {
            "title":           article.title,
            "slug":            article.slug,
            "content":         full_content,
            "excerpt":         article.excerpt,
            "status":          status,
            "tags":            tag_ids,
            "categories":      [cat_id] if cat_id else [],
            "meta": {
                "_yoast_wpseo_metadesc":       article.meta_description,
                "_yoast_wpseo_focuskw":        article.seo_keywords[0] if article.seo_keywords else "",
            },
        }

        try:
            r = httpx.post(
                f"{self.base_url}/posts",
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            result = r.json()
            if r.status_code in (200, 201):
                print(f"  ✅ WordPress: Published → {result.get('link', '')}")
                return {"success": True, "url": result.get("link"), "id": result.get("id")}
            else:
                print(f"  ❌ WordPress error: {r.status_code} — {result.get('message', '')}")
                return {"success": False, "error": result}
        except Exception as e:
            print(f"  ❌ WordPress exception: {e}")
            return {"success": False, "error": str(e)}


# ── STATIC SITE GENERATOR ─────────────────────────────────────────────────────

REGISTRY_FILE = "articles.json"


class StaticSiteGenerator:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.posts_dir = self.output_dir / "posts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        # In-memory list for articles published this run
        self.published_articles: List[GeneratedArticle] = []
        # Persistent registry loaded from disk (all articles ever published)
        self._registry: List[dict] = self._load_registry()

    # ── Registry helpers ──────────────────────────────────────────────────────

    def _load_registry(self) -> List[dict]:
        """Load the persistent article registry from disk (if it exists)."""
        registry_path = self.output_dir / REGISTRY_FILE
        if registry_path.exists():
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8"))
                print(f"  📚 Registry loaded: {len(data)} existing articles")
                return data
            except Exception as e:
                print(f"  ⚠️  Could not read registry, starting fresh: {e}")
        return []

    def _save_registry(self):
        """Persist the article registry to disk."""
        registry_path = self.output_dir / REGISTRY_FILE
        registry_path.write_text(
            json.dumps(self._registry, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _article_to_record(self, article: GeneratedArticle) -> dict:
        """Serialize an article's metadata to a registry record."""
        return {
            "slug":             article.slug,
            "title":            article.title,
            "excerpt":          article.excerpt,
            "category":         article.category,
            "tags":             article.tags[:5],
            "word_count":       article.word_count,
            "published_at":     datetime.utcnow().isoformat() + "Z",
        }

    def _upsert_registry(self, article: GeneratedArticle):
        """Add article to registry if not already present (keyed on slug)."""
        existing_slugs = {r["slug"] for r in self._registry}
        if article.slug not in existing_slugs:
            self._registry.append(self._article_to_record(article))

    # ── Public API ────────────────────────────────────────────────────────────

    def publish(self, article: GeneratedArticle) -> dict:
        """Write article to static HTML file and register it."""
        content = self._render_article_page(article)
        filepath = self.posts_dir / f"{article.slug}.html"
        filepath.write_text(content, encoding="utf-8")
        self.published_articles.append(article)
        self._upsert_registry(article)
        self._save_registry()
        url = f"{SITE_URL}/posts/{article.slug}.html"
        print(f"  ✅ Static: Written → {filepath.name}")
        return {"success": True, "url": url, "path": str(filepath)}

    def build_index(self) -> str:
        """Build the main index.html from the full persistent registry."""
        # Most-recent articles first
        all_articles = list(reversed(self._registry))
        cards_html = ""
        for record in all_articles:
            slug      = record["slug"]
            title     = record["title"]
            excerpt   = record["excerpt"]
            category  = record["category"]
            tags      = record.get("tags", [])
            wc        = record.get("word_count", 0)
            read_time = max(1, wc // 200)
            tag_html  = "".join(f'<span class="tag">{t}</span>' for t in tags[:3])
            cards_html += f"""
            <article class="post-card">
                <div class="post-meta">
                    <span class="category">{category}</span>
                    <span class="read-time">~{read_time} min read</span>
                </div>
                <h2><a href="posts/{slug}.html">{title}</a></h2>
                <p class="excerpt">{excerpt}</p>
                <div class="tags">{tag_html}</div>
                <a href="posts/{slug}.html" class="read-more">Read article →</a>
            </article>"""

        index = INDEX_TEMPLATE.replace("{{POSTS}}", cards_html)
        index_path = self.output_dir / "index.html"
        index_path.write_text(index, encoding="utf-8")
        print(f"  ✅ Index built: {len(all_articles)} articles (all-time)")
        self.build_sitemap()
        return str(index_path)

    def build_sitemap(self) -> str:
        """Generate sitemap.xml from the full persistent registry."""
        urls = [f"""
        <url>
            <loc>{SITE_URL}/</loc>
            <changefreq>daily</changefreq>
            <priority>1.0</priority>
        </url>"""]

        for record in self._registry:
            slug = record["slug"]
            lastmod = record.get("published_at", "")[:10]  # YYYY-MM-DD
            lastmod_tag = f"\n            <lastmod>{lastmod}</lastmod>" if lastmod else ""
            urls.append(f"""
        <url>
            <loc>{SITE_URL}/posts/{slug}.html</loc>{lastmod_tag}
            <changefreq>monthly</changefreq>
            <priority>0.8</priority>
        </url>""")

        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {''.join(urls)}
    </urlset>"""

        path = self.output_dir / "sitemap.xml"
        path.write_text(sitemap, encoding="utf-8")
        print(f"  ✅ Sitemap: {len(urls)} URLs written")
        return str(path)
      
    def _render_article_page(self, article: GeneratedArticle) -> str:
        """Render article to full HTML page."""
        content_with_ads = wrap_with_ads(article.content_html)
        return ARTICLE_TEMPLATE.format(
            title=article.title,
            meta_description=article.meta_description,
            site_name=SITE_NAME,
            site_url=SITE_URL,
            category=article.category,
            word_count=article.word_count,
            read_time=article.word_count // 200,
            tags=" · ".join(article.tags[:5]),
            content=content_with_ads,
            slug=article.slug,
            adsense_pub=ADSENSE_PUBLISHER_ID,
            adsense_slot=ADSENSE_SLOT_ID,
        )

# ── MAILCHIMP NEWSLETTER ───────────────────────────────────────────────────────

class MailchimpPublisher:
    def __init__(self):
        # Extract datacenter from API key (e.g., "us6")
        self.dc = MAILCHIMP_API_KEY.split("-")[-1] if MAILCHIMP_API_KEY else "us1"
        self.base_url = f"https://{self.dc}.api.mailchimp.com/3.0"
        self.headers = {
            "Authorization": f"apikey {MAILCHIMP_API_KEY}",
            "Content-Type": "application/json",
        }

    def create_campaign(self, subject: str, preview_text: str,
                        html_body: str) -> dict:
        """Create and send a Mailchimp newsletter campaign."""
        if not MAILCHIMP_API_KEY:
            print("  [SKIP] Mailchimp not configured")
            return {}

        # Create campaign
        campaign_data = {
            "type": "regular",
            "recipients": {"list_id": MAILCHIMP_LIST_ID},
            "settings": {
                "subject_line": subject,
                "preview_text": preview_text,
                "title":        f"{SITE_NAME} — {datetime.now().strftime('%b %d, %Y')}",
                "from_name":    SITE_NAME,
                "reply_to":     f"newsletter@{SITE_URL.replace('https://', '')}",
            },
        }

        try:
            r = httpx.post(
                f"{self.base_url}/campaigns",
                headers=self.headers,
                json=campaign_data,
            )
            campaign = r.json()
            campaign_id = campaign.get("id")

            if not campaign_id:
                return {"success": False, "error": campaign}

            # Set campaign content
            httpx.put(
                f"{self.base_url}/campaigns/{campaign_id}/content",
                headers=self.headers,
                json={"html": html_body},
            )

            print(f"  ✅ Mailchimp: Campaign created (id={campaign_id})")
            return {"success": True, "campaign_id": campaign_id}

        except Exception as e:
            print(f"  ❌ Mailchimp error: {e}")
            return {"success": False, "error": str(e)}


# ── HELPERS ────────────────────────────────────────────────────────────────────

def wrap_with_ads(content_html: str) -> str:
    """Insert AdSense ad unit after first H2 and at end of content."""
    ad_unit = f"""
<div class="ad-unit" style="margin:2rem 0;text-align:center;">
  <!-- AdSense -->
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="{ADSENSE_PUBLISHER_ID}"
       data-ad-slot="{ADSENSE_SLOT_ID}"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
  <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>"""

    affiliate_disclaimer = """
<div class="affiliate-notice" style="background:#f8f9fa;border-left:4px solid #0070f3;
     padding:0.75rem 1rem;margin:1.5rem 0;font-size:0.85rem;color:#666;">
  <strong>Disclosure:</strong> Some links in this article are affiliate links.
  We may earn a commission at no extra cost to you if you purchase through them.
</div>"""

    # Insert ad after first </h2>
    content_html = content_html.replace("</h2>", "</h2>" + ad_unit, 1)
    # Append disclaimer and closing ad
    return affiliate_disclaimer + content_html + ad_unit


# ── HTML TEMPLATES ─────────────────────────────────────────────────────────────

ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {site_name}</title>
  <meta name="description" content="{meta_description}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_description}">
  <meta property="og:type" content="article">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="{site_url}/posts/{slug}.html">
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{adsense_pub}}" crossorigin="anonymous"></script>
  <style>
    :root {{
      --font-sans: 'Georgia', serif;
      --font-mono: 'Courier New', monospace;
      --max-width: 760px;
      --color-text: #1a1a2e;
      --color-accent: #00c896;
      --color-muted: #666;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: var(--font-sans); color: var(--color-text);
            line-height: 1.7; background: #fff; }}
    .site-header {{ background: #0a0f1e; color: #fff; padding: 1rem 2rem;
                    display: flex; align-items: center; gap: 1rem; }}
    .site-header a.logo {{ color: #00c896; text-decoration: none; font-weight: bold; font-size: 1.2rem; }}
    .site-header nav {{ margin-left: auto; display: flex; gap: 1.5rem; }}
    .site-header nav a {{ color: #aaa; text-decoration: none; font-size: 0.9rem; font-weight: normal; }}
    .site-header nav a:hover {{ color: #fff; }}
    .article-container {{ max-width: var(--max-width); margin: 0 auto; padding: 2rem 1.5rem; }}
    .article-meta {{ color: var(--color-muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}
    h1 {{ font-size: clamp(1.6rem, 4vw, 2.4rem); line-height: 1.2;
          margin-bottom: 1.5rem; color: #0a0f1e; }}
    h2 {{ font-size: 1.5rem; margin: 2.5rem 0 1rem; color: #0a0f1e; }}
    h3 {{ font-size: 1.2rem; margin: 2rem 0 0.75rem; }}
    p {{ margin-bottom: 1.25rem; }}
    ul, ol {{ margin: 1rem 0 1.5rem 1.5rem; }}
    li {{ margin-bottom: 0.4rem; }}
    code {{ background: #f4f4f4; padding: 0.15rem 0.4rem;
            border-radius: 3px; font-family: var(--font-mono); font-size: 0.9em; }}
    pre {{ background: #0a0f1e; color: #e0e0e0; padding: 1.25rem;
       border-radius: 8px; overflow-x: auto; margin: 1.5rem 0;
       position: relative; }}
    pre .filename {{ display: block; color: #00c896; font-size: 0.8rem;
                 margin-bottom: 0.75rem; font-family: var(--font-mono); }}
    pre code {{ background: none; padding: 0; color: inherit; }}
    pre .code-filename {{ display: block; color: #00c896; font-size: 0.8rem;
                      font-family: var(--font-mono); margin-bottom: 0.5rem;
                      opacity: 0.8; }}
    .affiliate-link {{ color: var(--color-accent); font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0; }}
    th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #eee; }}
    th {{ background: #f4f4f4; font-weight: bold; }}
    .tags {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #eee;
             color: var(--color-muted); font-size: 0.85rem; }}
    footer {{ background: #0a0f1e; color: #888; text-align: center;
              padding: 2rem; margin-top: 4rem; font-size: 0.85rem; }}
  </style>
</head>

<body>
  <header class="site-header">
    <a href="/" class="logo">{site_name}</a>
    <nav>
      <a href="/">Articles</a>
      <a href="/about.html">About</a>
      <a href="/privacy.html">Privacy</a>
    </nav>
  </header>
  <main class="article-container">
    <div class="article-meta">
      <span>{category}</span> &middot;
      <span>{read_time} min read</span> &middot;
      <span>{word_count:,} words</span>
    </div>
    <h1>{title}</h1>
    <div class="article-content">
      {content}
    </div>
    <div class="tags">Tags: {tags}</div>
  </main>
  <footer>
    <p>&copy; {site_name} · <a href="/about.html" style="color:#888">About</a> ·
    <a href="/privacy.html" style="color:#888">Privacy</a> ·
    <a href="/affiliate-disclosure.html" style="color:#888">Affiliate Disclosure</a></p>
  </footer>
</body>
</html>"""


INDEX_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{SITE_NAME} — {SITE_URL}</title>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_PUBLISHER_ID}" crossorigin="anonymous"></script>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Georgia', serif; color: #1a1a2e; background: #f9f9f9; }}
    .site-nav {{ background: #0a0a1a; display: flex; align-items: center; padding: 0.85rem 2rem; gap: 1rem; }}
    .site-nav a.logo {{ color: #00c896; text-decoration: none; font-weight: bold; font-size: 1.1rem; }}
    .site-nav nav {{ margin-left: auto; display: flex; gap: 1.5rem; }}
    .site-nav nav a {{ color: #aaa; text-decoration: none; font-size: 0.9rem; }}
    .site-nav nav a:hover {{ color: #fff; }}
    .hero {{ background: #0a0a1a; color: #fff; padding: 4rem 2rem; text-align: center; }}
    .hero h1 {{ font-size: clamp(2rem, 5vw, 3.5rem); margin-bottom: 1rem; }}
    .hero p {{ color: #aaa; font-size: 1.15rem; max-width: 500px; margin: 0 auto 2rem; }}
    .newsletter-form {{ display: flex; gap: .75rem; justify-content: center; flex-wrap: wrap; }}
    .newsletter-form input {{ padding: .75rem 1rem; border: none; border-radius: 6px;
                               font-size: 1rem; width: 280px; }}
    .newsletter-form button {{ background: #0070f3; color: #fff; border: none; padding: .75rem 1.5rem;
                                border-radius: 6px; font-size: 1rem; cursor: pointer; font-weight: bold; }}
    .posts-grid {{ max-width: 1100px; margin: 3rem auto; padding: 0 1.5rem;
                   display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 2rem; }}
    .post-card {{ background: #fff; border-radius: 12px; padding: 1.75rem;
                  box-shadow: 0 2px 12px rgba(0,0,0,.08); transition: transform .2s; }}
    .post-card:hover {{ transform: translateY(-3px); box-shadow: 0 6px 24px rgba(0,0,0,.12); }}
    .post-meta {{ display: flex; gap: .75rem; font-size: .8rem; color: #888; margin-bottom: .75rem; }}
    .category {{ background: #e8f0ff; color: #0070f3; padding: .2rem .5rem; border-radius: 4px; }}
    .post-card h2 {{ font-size: 1.15rem; line-height: 1.4; margin-bottom: .75rem; }}
    .post-card h2 a {{ color: #0a0a1a; text-decoration: none; }}
    .post-card h2 a:hover {{ color: #0070f3; }}
    .excerpt {{ color: #555; font-size: .9rem; line-height: 1.6; margin-bottom: 1rem; }}
    .tags {{ display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1rem; }}
    .tag {{ background: #f0f0f0; color: #555; padding: .15rem .5rem; border-radius: 3px; font-size: .75rem; }}
    .read-more {{ color: #0070f3; font-weight: bold; font-size: .9rem; text-decoration: none; }}
    footer {{ background: #0a0a1a; color: #888; text-align: center; padding: 2rem; font-size: .85rem; }}
    footer a {{ color: #888; }}
  </style>
</head>
<body>
  <div class="site-nav">
    <a href="/" class="logo">{SITE_NAME}</a>
    <nav>
      <a href="/">Articles</a>
      <a href="/about.html">About</a>
      <a href="/privacy.html">Privacy</a>
    </nav>
  </div>
  <header class="hero">
    <h1>{SITE_NAME}</h1>
    <p>AI-powered insights for software testing professionals</p>
    <div class="newsletter-form">
      <input type="email" placeholder="your@email.com">
      <button>Get Weekly Digest →</button>
    </div>
  </header>
  <div class="posts-grid">
    {{{{POSTS}}}}
  </div>
  <footer>
    <p>&copy; {SITE_NAME} · <a href="/about.html">About</a> · <a href="/privacy.html">Privacy</a> · 
    <a href="/affiliate-disclosure.html">Affiliate Disclosure</a></p>
  </footer>
</body>
</html>"""