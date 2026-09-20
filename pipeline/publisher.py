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
import re
import sys
from base64 import b64encode
from datetime import datetime
from html import escape
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import (
    WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PW,
    MAILCHIMP_API_KEY, MAILCHIMP_LIST_ID,
    SITE_NAME, SITE_URL, ADSENSE_PUBLISHER_ID, ADSENSE_SLOT_ID,
    OUTPUT_DIR, AI_DISCLOSURE, LISTING_WINDOW_MONTHS,
    MIN_IN_ARTICLE_AD_WORDS,
)
from pipeline.featured_image import (
    EXTENSIONS as FEATURED_IMAGE_EXTS,
    IMAGE_DIR as FEATURED_IMAGE_DIR,
    ensure_featured_image,
    featured_image_alt,
)
from pipeline.generator import GeneratedArticle
from pipeline.chrome import SITE_CHROME_CSS, site_footer_html, site_nav_html
from pipeline.listings import (
    archive_by_month, featured_and_recent, listed_articles, read_time_minutes,
)


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

        # Wrap content with AdSense + affiliate disclaimer (capped at 1 unit)
        full_content = wrap_with_ads(article.content_html, article.word_count)

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

    def restore_existing_posts(self) -> None:
        """Copy already-published post HTML into the output dir so a deploy does not drop the archive."""
        import io, shutil, subprocess, tarfile, tempfile

        repo_root = Path(__file__).resolve().parent.parent
        dest = self.posts_dir
        dest.mkdir(parents=True, exist_ok=True)

        def extract(ref: str) -> int:
            proc = subprocess.run(
                ["git", "archive", "--format=tar", ref, "posts"],
                cwd=repo_root, capture_output=True,
            )
            if proc.returncode != 0:
                return len(list(dest.glob("*.html")))
            with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as tar:
                with tempfile.TemporaryDirectory() as tmp:
                    tar.extractall(tmp)
                    src = Path(tmp) / "posts"
                    if src.exists():
                        for f in src.glob("*.html"):
                            target = dest / f.name
                            if not target.exists():
                                shutil.copy2(f, target)
            return len(list(dest.glob("*.html")))

        subprocess.run(
            ["git", "fetch", "origin", "gh-pages", "--depth=50"],
            cwd=repo_root, capture_output=True,
        )
        n = extract("origin/gh-pages")
        if n < 10:
            n = extract("8f4aba764f")
        print(f"  📚 Restored {n} existing post HTML files")

    def restore_existing_drafts(self) -> None:
        """Copy pending draft JSON into the output dir so a deploy does not drop unpublished reviews."""
        import io, shutil, subprocess, tarfile, tempfile

        repo_root = Path(__file__).resolve().parent.parent
        dest = self.output_dir / "drafts"
        dest.mkdir(parents=True, exist_ok=True)

        def extract(ref: str) -> int:
            proc = subprocess.run(
                ["git", "archive", "--format=tar", ref, "drafts"],
                cwd=repo_root, capture_output=True,
            )
            if proc.returncode != 0:
                return len(list(dest.glob("*.json")))
            with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as tar:
                with tempfile.TemporaryDirectory() as tmp:
                    tar.extractall(tmp)
                    src = Path(tmp) / "drafts"
                    if src.exists():
                        for f in src.glob("*.json"):
                            target = dest / f.name
                            if not target.exists():
                                shutil.copy2(f, target)
            return len(list(dest.glob("*.json")))

        n = extract("origin/gh-pages")
        print(f"  📚 Restored {n} pending draft JSON files")

    def restore_featured_images(self) -> None:
        """Copy cached featured images from gh-pages so a slug is never regenerated."""
        import io, shutil, subprocess, tarfile, tempfile

        repo_root = Path(__file__).resolve().parent.parent
        dest = self.output_dir / FEATURED_IMAGE_DIR
        dest.mkdir(parents=True, exist_ok=True)

        def extract(ref: str) -> int:
            proc = subprocess.run(
                ["git", "archive", "--format=tar", ref, FEATURED_IMAGE_DIR],
                cwd=repo_root, capture_output=True,
            )
            if proc.returncode != 0:
                return len([p for p in dest.iterdir() if p.is_file()])
            with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as tar:
                with tempfile.TemporaryDirectory() as tmp:
                    tar.extractall(tmp)
                    src = Path(tmp) / FEATURED_IMAGE_DIR
                    if src.exists():
                        for f in src.iterdir():
                            if f.is_file() and f.suffix.lower() in FEATURED_IMAGE_EXTS:
                                target = dest / f.name
                                if not target.exists():
                                    shutil.copy2(f, target)
            return len([p for p in dest.iterdir() if p.is_file()])

        n = extract("origin/gh-pages")
        print(f"  📚 Restored {n} featured image cache file(s)")

    def publish(self, article: GeneratedArticle) -> dict:
        """Write article to static HTML file and register it."""
        self.restore_existing_posts()
        self.restore_existing_drafts()
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
        """Build homepage: Article of the Week + a few recent cards."""
        featured, recent = featured_and_recent(self._registry)
        listed = listed_articles(self._registry)
        self.restore_featured_images()
        image_rel = ensure_featured_image(featured, self.output_dir) if featured else None
        index = INDEX_TEMPLATE.replace(
            "{{FEATURED}}", self._render_featured(featured, image_rel)
        )
        index = index.replace("{{RECENT}}", self._render_recent(recent))
        index_path = self.output_dir / "index.html"
        index_path.write_text(index, encoding="utf-8")
        print(f"  ✅ Index built: featured week + {len(recent)} recent "
              f"({len(listed)} listed / {len(self._registry)} all-time)")
        self.build_archive()
        self.build_sitemap()
        self.copy_static_assets()
        self.sanitize_post_ad_units()
        return str(index_path)

    def _render_featured_panel(self, record: Optional[dict],
                               image_rel: Optional[str]) -> str:
        """Image when cached/generated; otherwise the solid teal box."""
        if image_rel and record:
            title = record.get("title") or record.get("slug") or "featured article"
            alt = escape(featured_image_alt(title), quote=True)
            src = escape(image_rel, quote=True)
            return (
                f'<div class="featured-panel">'
                f'<img src="{src}" alt="{alt}" width="768" height="1024">'
                f"</div>"
            )
        return '<div class="featured-panel" aria-hidden="true"></div>'

    def _render_featured(self, record: Optional[dict],
                         image_rel: Optional[str] = None) -> str:
        panel = self._render_featured_panel(record, image_rel)
        if not record:
            return f"""
            <section class="featured-week">
              <div class="featured-copy">
                <span class="badge">Article of the Week</span>
                <h1>New writing is on the way</h1>
                <p class="pitch">Hands-on notes on Java, GitLab AppSec, and
                the developer-as-security-champion dual role.</p>
                <a href="/archive.html" class="cta">Browse the archive</a>
              </div>
              {panel}
            </section>"""
        slug = record["slug"]
        return f"""
            <section class="featured-week">
              <div class="featured-copy">
                <span class="badge">Article of the Week</span>
                <h1>{record["title"]}</h1>
                <p class="pitch">{record.get("excerpt", "")}</p>
                <a href="posts/{slug}.html" class="cta">Read article</a>
              </div>
              {panel}
            </section>"""

    def _render_recent(self, records: List[dict]) -> str:
        if not records:
            return """
            <section class="recent-block">
              <div class="recent-header">
                <h2>Recent</h2>
                <a href="/archive.html">Full archive →</a>
              </div>
              <p class="empty-recent">No other recent posts in the last year yet.</p>
            </section>"""
        cards = []
        for record in records:
            slug = record["slug"]
            read_time = read_time_minutes(record)
            cards.append(f"""
              <article class="recent-card">
                <a class="recent-card-link" href="posts/{slug}.html">
                  <span class="category">{record.get("category", "")}</span>
                  <h3>{record["title"]}</h3>
                  <p>{record.get("excerpt", "")}</p>
                  <span class="read-time">~{read_time} min read</span>
                </a>
              </article>""")
        return f"""
            <section class="recent-block">
              <div class="recent-header">
                <h2>Recent</h2>
                <a href="/archive.html">Full archive →</a>
              </div>
              <div class="recent-grid">
                {''.join(cards)}
              </div>
            </section>"""

    def build_archive(self) -> str:
        """Build archive.html — last ~12 months, grouped by month."""
        groups = archive_by_month(self._registry)
        sections = []
        total = 0
        for label, articles in groups:
            items = []
            for record in articles:
                slug = record["slug"]
                read_time = read_time_minutes(record)
                items.append(
                    f'<li><a href="posts/{slug}.html">{record["title"]}</a>'
                    f'<span>~{read_time} min</span></li>'
                )
                total += 1
            sections.append(f"""
            <section class="month-group">
              <h2>{label}</h2>
              <ul class="archive-list">
                {''.join(items)}
              </ul>
            </section>""")
        body = "".join(sections) or "<p>No posts in the last 12 months.</p>"
        html = ARCHIVE_TEMPLATE.replace("{{MONTHS}}", body)
        path = self.output_dir / "archive.html"
        path.write_text(html, encoding="utf-8")
        print(f"  ✅ Archive built: {total} posts in {len(groups)} month(s)")
        return str(path)

    def sanitize_post_ad_units(self) -> int:
        """Cap manual AdSense units already written to posts/*.html.

        Pages rebuilds restore live HTML from gh-pages. Older articles may
        still have an in-article unit after the first H2 plus an end unit.
        Reduce those to the current cap without rewriting article copy.
        """
        if not self.posts_dir.exists():
            return 0
        changed = 0
        for path in sorted(self.posts_dir.glob("*.html")):
            original = path.read_text(encoding="utf-8")
            updated = cap_manual_ad_units(original)
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                changed += 1
        if changed:
            print(f"  ✅ Ad density: capped manual units in {changed} post(s)")
        return changed

    def build_sitemap(self) -> str:
        """Generate a clean, valid sitemap.xml."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            '  <url>',
            f'    <loc>{SITE_URL}/</loc>',
            '    <changefreq>daily</changefreq>',
            '    <priority>1.0</priority>',
            '  </url>',
        ]

        # Static pages
        static_pages = [
            ("archive.html", "0.8"),
            ("about.html", "0.7"),
            ("privacy.html", "0.4"),
            ("affiliate-disclosure.html", "0.3"),
        ]
        for page, priority in static_pages:
            lines.extend([
                '  <url>',
                f'    <loc>{SITE_URL}/{page}</loc>',
                '    <changefreq>monthly</changefreq>',
                f'    <priority>{priority}</priority>',
                '  </url>',
            ])

        # Articles
        for record in self._registry:
            slug = record["slug"]
            lastmod = record.get("published_at", "")[:10]
            lines.append('  <url>')
            lines.append(f'    <loc>{SITE_URL}/posts/{slug}.html</loc>')
            if lastmod:
                lines.append(f'    <lastmod>{lastmod}</lastmod>')
            lines.append('    <changefreq>monthly</changefreq>')
            lines.append('    <priority>0.8</priority>')
            lines.append('  </url>')

        lines.append('</urlset>')
        lines.append('')  # trailing newline

        sitemap = '\n'.join(lines)
        path = self.output_dir / "sitemap.xml"
        path.write_text(sitemap, encoding="utf-8")
        print(f"  ✅ Sitemap: {len(self._registry) + 1 + len(static_pages)} URLs written")
        return str(path)
      
    def _render_article_page(self, article: GeneratedArticle) -> str:
        """Render article to full HTML page."""
        content_with_ads = wrap_with_ads(article.content_html, article.word_count)
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
            ai_disclosure=AI_DISCLOSURE,
        )

    def copy_static_assets(self) -> None:
        """Copy everything from static/ into the output directory (robots.txt, about, privacy, favicons, etc.)."""
        import shutil
        static_dir = Path(__file__).resolve().parent.parent / "static"
        if not static_dir.exists():
            print("  ⚠️  static/ directory not found — skipping asset copy")
            return

        for item in static_dir.iterdir():
            dest = self.output_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
            elif item.is_dir():
                # Merge into dest. Never delete generated article HTML.
                dest.mkdir(parents=True, exist_ok=True)
                for child in item.iterdir():
                    target = dest / child.name
                    if child.is_file():
                        if item.name == "posts" and target.exists():
                            continue
                        shutil.copy2(child, target)
                    elif child.is_dir():
                        # Merge featured-image cache. Never rmtree generated slugs.
                        if item.name == "images":
                            dest.mkdir(parents=True, exist_ok=True)
                            target.mkdir(parents=True, exist_ok=True)
                            for img in child.iterdir():
                                if img.is_file() and not (target / img.name).exists():
                                    shutil.copy2(img, target / img.name)
                            continue
                        if target.exists():
                            shutil.rmtree(target)
                        shutil.copytree(child, target)
        print(f"  ✅ Static assets copied from {static_dir}")

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

# Manual in-article units only. The page <head> still loads adsbygoogle.js so
# Auto ads can run if enabled — Chris should disable Auto ads in the AdSense UI
# until the "low value content" review passes. Publisher id is not changed here
# (live value: ca-pub-9384256595608147 via ADSENSE_PUB_ID).
_HEADING_CLOSE_RE = re.compile(r"</h[23]>", re.IGNORECASE)
_AD_UNIT_RE = re.compile(
    r'\s*<div class="ad-unit"[^>]*>.*?</div>',
    re.IGNORECASE | re.DOTALL,
)
_ARTICLE_BODY_RE = re.compile(
    r'<div class="article-content">(.*)</div>\s*<div class="tags">',
    re.IGNORECASE | re.DOTALL,
)


def html_word_count(html: str) -> int:
    """Approximate visible-word count from HTML (scripts/styles stripped)."""
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(text.split())


def article_body_word_count(html: str) -> int:
    """Word count of the article body, falling back to the full document."""
    match = _ARTICLE_BODY_RE.search(html)
    return html_word_count(match.group(1) if match else html)


def _manual_ad_unit() -> str:
    return f"""
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


def _insert_after_second_heading(content_html: str, ad_unit: str) -> str:
    """Prefer mid-article (after the 2nd H2/H3). Otherwise a single end unit."""
    matches = list(_HEADING_CLOSE_RE.finditer(content_html))
    if len(matches) >= 2:
        pos = matches[1].end()
        return content_html[:pos] + ad_unit + content_html[pos:]
    return content_html + ad_unit


def wrap_with_ads(content_html: str, word_count: Optional[int] = None) -> str:
    """Insert at most one manual AdSense unit, or none on short posts.

    Rules (AdSense low-value-content remediation):
    - Under ~900 body words: no in-article unit. adsbygoogle.js may still load
      in the page head for Auto ads (disable those in the AdSense UI).
    - Long enough: one unit after the 2nd heading, or at the end if there
      are fewer than two headings.
    - Never inject after the first H2 on short posts.
    """
    affiliate_disclaimer = """
<div class="affiliate-notice" style="background:#f8f9fa;border-left:4px solid #0070f3;
     padding:0.75rem 1rem;margin:1.5rem 0;font-size:0.85rem;color:#666;">
  <strong>Disclosure:</strong> Some links in this article are affiliate links.
  We may earn a commission at no extra cost to you if you purchase through them.
</div>"""

    words = word_count if word_count is not None else html_word_count(content_html)
    if words < MIN_IN_ARTICLE_AD_WORDS:
        return affiliate_disclaimer + content_html

    placed = _insert_after_second_heading(content_html, _manual_ad_unit())
    return affiliate_disclaimer + placed


def cap_manual_ad_units(html: str, word_count: Optional[int] = None) -> str:
    """Reduce existing article HTML to the current in-article ad cap.

    Keeps the adsbygoogle.js loader and hide-unfilled CSS. Does not change
    publisher id. Used when --mode pages restores already-published posts.
    """
    words = word_count if word_count is not None else article_body_word_count(html)
    units = list(_AD_UNIT_RE.finditer(html))
    if not units:
        return html
    if words < MIN_IN_ARTICLE_AD_WORDS:
        return _AD_UNIT_RE.sub("", html)
    if len(units) == 1:
        return html
    # Keep a single end unit. Older HTML often injected after the first H2;
    # dropping those extra early units is the density fix.
    keep = units[-1]
    pieces = []
    cursor = 0
    for match in units:
        if match is keep:
            continue
        pieces.append(html[cursor:match.start()])
        cursor = match.end()
    pieces.append(html[cursor:])
    return "".join(pieces)


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
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-4DZEHG6QFW"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-4DZEHG6QFW');
  </script>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <!-- adsbygoogle.js loader only: no extra manual units here. Disable Auto ads
       in the AdSense UI during low-value-content remediation. Publisher:
       ca-pub-9384256595608147 -->
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={adsense_pub}" crossorigin="anonymous"></script>
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
    .ai-disclosure {{ color: #9aa3ad; max-width: 640px; margin: 0 auto 0.85rem;
                     font-size: 0.82rem; line-height: 1.5; }}
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
    ins.adsbygoogle[data-ad-status="unfilled"] {{ display: none !important; height: 0 !important; }}
    .ad-unit:has(ins[data-ad-status="unfilled"]) {{ display: none; margin: 0 !important; }}
  </style>
</head>

<body>
  <header class="site-header">
    <a href="/" class="logo">{site_name}</a>
    <nav>
      <a href="/">Home</a>
      <a href="/archive.html">Archive</a>
      <a href="/about.html">About</a>
    </nav>
  </header>
  <main class="article-container">
    <div class="article-meta">
      <span>{category}</span> &middot;
      <span>{read_time} min read</span> &middot;
      <span>{word_count:,} words</span>
    </div>
    <h1>{title}</h1>
        <p class="author-byline" style="margin-top:-0.75rem;margin-bottom:1.75rem;color:var(--color-muted);font-size:0.95rem;">
        By <a href="/about.html" style="color:var(--color-accent);text-decoration:none;font-weight:600;">Chris Clark</a>
        · AppSec practitioner &amp; AWS Solutions Architect
        </p>
        <div class="article-content">
        {content}
        </div>
    <div class="tags">Tags: {tags}</div>
  </main>
  <footer>
    <p class="ai-disclosure">{ai_disclosure}</p>
    <p>&copy; {site_name} · <a href="/archive.html" style="color:#888">Archive</a> ·
    <a href="/about.html" style="color:#888">About</a> ·
    <a href="/privacy.html" style="color:#888">Privacy</a> ·
    <a href="/affiliate-disclosure.html" style="color:#888">Affiliate Disclosure</a></p>
  </footer>
</body>
</html>"""


_LISTING_PAGE_CSS = """
    .featured-week { max-width: 1040px; margin: 2.5rem auto 0; padding: 0 1.5rem;
                     display: grid; grid-template-columns: 1.4fr 0.8fr; gap: 2rem;
                     align-items: stretch; }
    .featured-copy { background: var(--navy); color: #fff; border-radius: 16px;
                     padding: 2.75rem 2.5rem; }
    .badge { display: inline-block; font-family: var(--sans); font-size: 0.72rem;
             letter-spacing: 0.12em; text-transform: uppercase; color: var(--teal);
             font-weight: 700; margin-bottom: 1rem; }
    .featured-copy h1 { font-size: clamp(1.7rem, 4vw, 2.4rem); line-height: 1.2;
                        margin-bottom: 1rem; color: #fff; }
    .pitch { color: #c5cdd6; font-size: 1.05rem; max-width: 36rem;
             margin-bottom: 1.75rem; }
    .cta { display: inline-block; background: var(--teal); color: var(--navy);
           text-decoration: none; font-family: var(--sans); font-weight: 700;
           padding: 0.75rem 1.4rem; border-radius: 999px; }
    .cta:hover { background: #14d6a4; }
    .featured-panel { background: #14d4c8; border-radius: 16px; min-height: 220px;
                      overflow: hidden; aspect-ratio: 3 / 4; }
    .featured-panel img { display: block; width: 100%; height: 100%;
                          object-fit: cover; border-radius: 16px; }
    .recent-block { max-width: 1040px; margin: 2.75rem auto 3rem; padding: 0 1.5rem; }
    .recent-header { display: flex; align-items: baseline; justify-content: space-between;
                     margin-bottom: 1.25rem; }
    .recent-header h2 { font-size: 1.35rem; }
    .recent-header a { font-family: var(--sans); font-size: 0.9rem; }
    .recent-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.25rem; }
    .recent-card { background: var(--card); border-radius: 12px;
                   box-shadow: 0 2px 12px rgba(10,15,30,.06); border: 1px solid var(--line);
                   transition: transform .15s ease, box-shadow .15s ease; }
    .recent-card-link { display: block; padding: 1.4rem 1.35rem; text-decoration: none; color: inherit; }
    .recent-card:hover { box-shadow: 0 6px 18px rgba(10,15,30,.10); transform: translateY(-2px); }
    .recent-card .category { font-family: var(--sans); font-size: 0.72rem; color: var(--teal-dark);
                             text-transform: uppercase; letter-spacing: 0.06em; }
    .recent-card h3 { font-size: 1.05rem; line-height: 1.35; margin: 0.55rem 0 0.6rem; color: var(--navy); }
    .recent-card:hover h3 { color: var(--teal-dark); }
    .recent-card p { color: #555; font-size: 0.9rem; margin-bottom: 0.85rem; }
    .read-time, .empty-recent { color: var(--muted); font-size: 0.82rem; font-family: var(--sans); }
    .archive-wrap { max-width: 800px; margin: 0 auto; padding: 3rem 1.5rem 1rem; }
    .archive-wrap h1 { font-size: clamp(1.8rem, 4vw, 2.4rem); margin-bottom: 0.5rem; }
    .archive-lede { color: var(--muted); margin-bottom: 2.5rem; }
    .month-group { margin-bottom: 2.25rem; }
    .month-group h2 { font-size: 1.1rem; color: var(--navy); padding-bottom: 0.5rem;
                      border-bottom: 2px solid var(--line); margin-bottom: 0.85rem; }
    .archive-list { list-style: none; }
    .archive-list li { display: flex; justify-content: space-between; gap: 1rem;
                       padding: 0.7rem 0; border-bottom: 1px solid var(--line); }
    .archive-list a { color: var(--navy); text-decoration: none; font-weight: 600; }
    .archive-list a:hover { color: var(--teal-dark); }
    .archive-list span { color: var(--muted); font-size: 0.8rem; font-family: var(--sans);
                         white-space: nowrap; }
    .retire-note { margin-top: 2.5rem; padding-top: 1.25rem; border-top: 1px solid var(--line);
                   color: var(--muted); font-size: 0.9rem; }
    @media (max-width: 800px) {
      .featured-week, .recent-grid { grid-template-columns: 1fr; }
      .featured-panel { aspect-ratio: 1 / 1; min-height: 160px; }
    }
"""

INDEX_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{SITE_NAME} — Article of the Week</title>
  <meta name="description" content="{SITE_NAME}: featured weekly writing on Java, GitLab AppSec, and developer-as-security-champion work.">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_PUBLISHER_ID}" crossorigin="anonymous"></script>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-4DZEHG6QFW"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-4DZEHG6QFW');
  </script>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <style>
""" + SITE_CHROME_CSS + _LISTING_PAGE_CSS + f"""
  </style>
</head>
<body>
{site_nav_html("Home")}
  {{{{FEATURED}}}}
  {{{{RECENT}}}}
{site_footer_html()}
</body>
</html>"""

ARCHIVE_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Archive | {SITE_NAME}</title>
  <meta name="description" content="Posts from the last {LISTING_WINDOW_MONTHS} months on {SITE_NAME}.">
  <link rel="canonical" href="{SITE_URL}/archive.html">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-4DZEHG6QFW"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-4DZEHG6QFW');
  </script>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <style>
""" + SITE_CHROME_CSS + _LISTING_PAGE_CSS + f"""
  </style>
</head>
<body>
{site_nav_html("Archive")}
  <main class="archive-wrap">
    <h1>Archive</h1>
    <p class="archive-lede">Reverse-chronological posts from the last {LISTING_WINDOW_MONTHS} months, grouped by month.</p>
    {{{{MONTHS}}}}
    <p class="retire-note">Articles older than {LISTING_WINDOW_MONTHS} months, plus some older or thinner posts, may be omitted from this index. They are quietly retired from home and archive listings. Their permalinks stay live.</p>
  </main>
{site_footer_html()}
</body>
</html>"""