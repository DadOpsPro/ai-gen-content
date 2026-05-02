"""
pipeline/orchestrator.py
────────────────────────
The main pipeline runner. Ties together:
  scraper → generator → publisher → newsletter

Usage:
  python -m pipeline.orchestrator --mode seed     # Generate 15 seed articles
  python -m pipeline.orchestrator --mode daily    # Generate 1-2 articles + check trends
  python -m pipeline.orchestrator --mode newsletter  # Send weekly newsletter
  python -m pipeline.orchestrator --mode plan     # Print content calendar
"""

import argparse
import json
import time
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import (
    ANTHROPIC_API_KEY, OUTPUT_DIR, ARTICLES_PER_SEED_RUN, SITE_NAME
)
from pipeline.scraper import gather_trending_topics, TrendingTopic
from pipeline.generator import generate_article, generate_newsletter, plan_content_calendar
from pipeline.publisher import WordPressPublisher, StaticSiteGenerator, MailchimpPublisher


STATE_FILE = Path(__file__).parent.parent / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"published_slugs": [], "last_run": None, "article_count": 0}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def run_seed_pipeline(target_count: int = ARTICLES_PER_SEED_RUN):
    """
    Generate initial batch of SEO seed articles.
    Runs through the content calendar and publishes each article.
    """
    print(f"\n{'='*60}")
    print(f"🚀 SEED PIPELINE — Generating {target_count} articles")
    print(f"{'='*60}")

    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set. Check your .env file.")
        sys.exit(1)

    state = load_state()
    calendar = plan_content_calendar(target_count)
    static_gen = StaticSiteGenerator()
    wp_pub = WordPressPublisher() if os.getenv("WORDPRESS_URL") else None

    published_articles = []
    errors = []

    for i, item in enumerate(calendar, 1):
        slug_hint = item["topic"][:30].lower().replace(" ", "-")
        if slug_hint in state["published_slugs"]:
            print(f"\n[{i}/{target_count}] SKIP (already published): {item['topic'][:50]}")
            continue

        print(f"\n[{i}/{target_count}] Generating: {item['topic'][:60]}")

        try:
            article = generate_article(
                topic=item["topic"],
                article_type=item["article_type"],
                keywords=item["keywords"],
            )

            # Publish to static site
            result = static_gen.publish(article)

            # Publish to WordPress if configured
            if wp_pub:
                wp_result = wp_pub.publish(article)
                if not wp_result.get("success"):
                    print(f"  ⚠️  WordPress publish failed (static OK)")

            state["published_slugs"].append(article.slug)
            state["article_count"] += 1
            published_articles.append(article)

            print(f"  ✅ Done: '{article.title}' ({article.word_count} words)")
            print(f"     Affiliates: {', '.join(article.affiliate_links_inserted) or 'none'}")

            # Rate limiting — be nice to the API
            if i < target_count:
                time.sleep(2)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            errors.append({"item": item["topic"], "error": str(e)})
            time.sleep(5)

    # Build the index page
    print("\n📄 Building site index...")
    static_gen.build_index()

    # Build static pages
    from pipeline.pages import build_all_pages
    build_all_pages()

    # Update state
    state["last_run"] = datetime.now().isoformat()
    save_state(state)

    # Summary
    print(f"\n{'='*60}")
    print(f"✅ SEED COMPLETE")
    print(f"   Published: {len(published_articles)} articles")
    print(f"   Errors:    {len(errors)}")
    print(f"   Output:    {OUTPUT_DIR}")
    print(f"{'='*60}")

    if errors:
        print("\n⚠️  Errors encountered:")
        for e in errors:
            print(f"  - {e['item']}: {e['error']}")

    return published_articles


def run_daily_pipeline():
    """
    Daily run: scrape trends, pick 1-2 topics, generate & publish.
    Schedule this with cron or GitHub Actions.
    """
    print(f"\n{'='*60}")
    print(f"📅 DAILY PIPELINE — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}")

    state = load_state()
    static_gen = StaticSiteGenerator()

    # 1. Gather fresh trends
    print("\n🔍 Gathering trends...")
    topics = gather_trending_topics(max_topics=20)

    if not topics:
        print("No new topics found. Using scheduled content.")
        calendar = plan_content_calendar(5)
        # Pick one not yet published
        for item in calendar:
            slug = item["topic"][:30].lower().replace(" ", "-")
            if slug not in state["published_slugs"]:
                topics_to_write = [item]
                break
        else:
            print("All scheduled content already published.")
            return
    else:
        # Pick top 2 trending topics
        topics_to_write = [
            {
                "topic":        t.title,
                "article_type": "trend_roundup" if i == 0 else "how_to_guide",
                "keywords":     t.keywords[:5],
                "context":      t.summary,
            }
            for i, t in enumerate(topics[:2])
        ]

    published = []
    for item in topics_to_write:
        try:
            article = generate_article(
                topic=item["topic"],
                article_type=item.get("article_type", "how_to_guide"),
                context=item.get("context", ""),
                keywords=item.get("keywords", []),
            )
            result = static_gen.publish(article)
            state["published_slugs"].append(article.slug)
            state["article_count"] += 1
            published.append(article)
            print(f"  ✅ Published: {article.title}")
            time.sleep(2)
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # Build static pages
    from pipeline.pages import build_all_pages
    build_all_pages()
    
    static_gen.build_index()
    state["last_run"] = datetime.now().isoformat()
    save_state(state)

    print(f"\n✅ Daily run complete: {len(published)} articles published")
    return published


def run_newsletter_pipeline():
    """Generate and send weekly newsletter from recent articles."""
    print(f"\n{'='*60}")
    print(f"📧 NEWSLETTER PIPELINE")
    print(f"{'='*60}")

    # Load recent articles from static site
    posts_dir = Path(OUTPUT_DIR) / "posts"
    if not posts_dir.exists():
        print("No articles found. Run seed pipeline first.")
        return

    # Read recent article metadata from state (simplified)
    state = load_state()
    recent_slugs = state["published_slugs"][-10:]

    # We'll generate a newsletter based on what we know
    from config.settings import TOPIC_CLUSTERS
    mock_articles = []  # In production, deserialize from saved JSON

    print("  Generating newsletter content...")
    # Generate newsletter copy
    newsletter_html = f"""
    <html><body style="font-family:Georgia,serif;max-width:600px;margin:0 auto;color:#1a1a2e">
    <h1 style="color:#0070f3">{SITE_NAME}</h1>
    <p>This week in AI testing: {len(recent_slugs)} new articles published.</p>
    <hr>
    <h2>Latest Articles</h2>
    {''.join(f'<p><a href="{os.getenv("SITE_URL", "#")}/posts/{s}.html">{s.replace("-", " ").title()}</a></p>' for s in recent_slugs[-5:])}
    <hr>
    <p style="font-size:.85rem;color:#888">
    You're receiving this because you subscribed to {SITE_NAME}.<br>
    <em>Some links may be affiliate links.</em>
    </p>
    </body></html>"""

    mc = MailchimpPublisher()
    result = mc.create_campaign(
        subject=f"🤖 {SITE_NAME}: This Week in AI Testing",
        preview_text="Fresh articles, tools, and trends for QA engineers",
        html_body=newsletter_html,
    )

    if result.get("success"):
        print(f"  ✅ Campaign created (id={result.get('campaign_id')})")
        print("  ℹ️  Campaign is in draft — review and send manually in Mailchimp")
    else:
        print(f"  ❌ Newsletter failed: {result}")


def print_content_calendar():
    """Print the planned content calendar."""
    calendar = plan_content_calendar(20)
    print(f"\n📅 CONTENT CALENDAR — {SITE_NAME}")
    print(f"{'─'*70}")
    print(f"{'#':<4} {'Type':<18} {'Topic':<46}")
    print(f"{'─'*70}")
    for item in calendar:
        print(f"{item['index']:<4} {item['article_type']:<18} {item['topic'][:45]}")
    print(f"{'─'*70}")
    print(f"Total: {len(calendar)} planned articles\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{SITE_NAME} Content Engine")
    parser.add_argument(
        "--mode",
        choices=["seed", "daily", "newsletter", "plan"],
        default="plan",
        help="Pipeline mode to run"
    )
    parser.add_argument("--count", type=int, default=ARTICLES_PER_SEED_RUN,
                       help="Number of articles for seed mode")
    args = parser.parse_args()

    if args.mode == "seed":
        run_seed_pipeline(args.count)
    elif args.mode == "daily":
        run_daily_pipeline()
    elif args.mode == "newsletter":
        run_newsletter_pipeline()
    elif args.mode == "plan":
        print_content_calendar()
