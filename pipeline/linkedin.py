"""
pipeline/linkedin.py
────────────────────
Generates LinkedIn post drafts from articles and manages
a file-based approval queue stored in linkedin_queue/.

Queue entry lifecycle:
  pending  → approval email sent, waiting for review
  approved → approved by Chris, scheduled to post at next 8am CT weekday
  posted   → successfully posted to LinkedIn
  rejected → skipped / will not post
"""

import json
import os
import sys
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import ANTHROPIC_API_KEY, SITE_NAME, SITE_URL

QUEUE_DIR = Path(__file__).parent.parent / "linkedin_queue"
QUEUE_DIR.mkdir(exist_ok=True)

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN   = os.getenv("LINKEDIN_PERSON_URN", "")   # urn:li:person:XXXXXXX
LINKEDIN_ORG_URN      = os.getenv("LINKEDIN_ORG_URN", "")      # urn:li:organization:XXXXXXX — use org if posting as company page


@dataclass
class LinkedInQueueEntry:
    slug: str
    title: str
    article_url: str
    excerpt: str
    tags: list
    post_draft: str
    status: str          # pending | approved | posted | rejected
    created_at: str
    approved_at: str = ""
    posted_at: str = ""
    scheduled_for: str = ""  # ISO datetime — post goes out at this time


# ── GENERATE POST DRAFT ───────────────────────────────────────────────────────

def generate_linkedin_post(article) -> str:
    """
    Use Claude to write a LinkedIn post draft from a GeneratedArticle.
    Speechify-friendly: short sentences, no jargon walls.
    """
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are writing a LinkedIn post for {SITE_NAME}, a publication about AI in software testing and application security.

Article title: {article.title}
Article excerpt: {article.excerpt}
Article URL: {SITE_URL}/posts/{article.slug}.html
Tags: {', '.join(article.tags[:5])}

Write a LinkedIn post that:
- Starts with a compelling hook (one short sentence — a question or bold statement)
- Has 3–4 short punchy lines about what readers will learn
- Uses simple, clear language (no jargon walls — it should sound natural when read aloud)
- Ends with a call to action to read the full article
- Includes 3–5 relevant hashtags at the bottom
- Is 150–200 words total
- Does NOT use bullet points with dashes — use line breaks between ideas instead

Return only the post text. No preamble, no commentary."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


# ── QUEUE MANAGEMENT ──────────────────────────────────────────────────────────

def queue_article(article) -> LinkedInQueueEntry:
    """Generate a LinkedIn post draft and add it to the pending queue."""
    queue_file = QUEUE_DIR / f"{article.slug}.json"
    
    # Don't overwrite if already exists — it may be approved or posted
    if queue_file.exists():
        existing = json.loads(queue_file.read_text())
        if existing.get("status") in ("approved", "posted", "rejected"):
            print(f"  ⏭ Skipping queue — already {existing['status']}: {article.slug}")
            return LinkedInQueueEntry(**existing)
    
    print(f"  📝 Generating LinkedIn post draft for: {article.title}")
    post_draft = generate_linkedin_post(article)

    entry = LinkedInQueueEntry(
        slug=article.slug,
        title=article.title,
        article_url=f"{SITE_URL}/posts/{article.slug}.html",
        excerpt=article.excerpt,
        tags=article.tags,
        post_draft=post_draft,
        status="pending",
        created_at=datetime.utcnow().isoformat(),
    )

    queue_file.write_text(json.dumps(asdict(entry), indent=2))
    print(f"  ✅ Queued: {queue_file.name}")
    return entry


def load_queue(status_filter: Optional[str] = None) -> list[LinkedInQueueEntry]:
    """Load all queue entries, optionally filtered by status."""
    entries = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            entry = LinkedInQueueEntry(**data)
            if status_filter is None or entry.status == status_filter:
                entries.append(entry)
        except Exception as e:
            print(f"  ⚠️  Could not load {f.name}: {e}")
    return entries


def update_queue_entry(slug: str, **updates):
    """Update fields on a queue entry by slug."""
    queue_file = QUEUE_DIR / f"{slug}.json"
    if not queue_file.exists():
        raise FileNotFoundError(f"No queue entry for slug: {slug}")
    data = json.loads(queue_file.read_text())
    data.update(updates)
    queue_file.write_text(json.dumps(data, indent=2))


def approve_article(slug: str):
    """Mark an article as approved and set its scheduled post time."""
    scheduled = _next_weekday_8am_ct()
    update_queue_entry(
        slug,
        status="approved",
        approved_at=datetime.utcnow().isoformat(),
        scheduled_for=scheduled.isoformat(),
    )
    print(f"  ✅ Approved: {slug} — scheduled for {scheduled.strftime('%A %b %d at 8:00 AM CT')}")


def reject_article(slug: str):
    """Mark an article as rejected — will not post to LinkedIn."""
    update_queue_entry(slug, status="rejected")
    print(f"  🚫 Rejected: {slug}")


# ── POSTING TO LINKEDIN ───────────────────────────────────────────────────────

def post_approved_articles():
    """
    Check the queue for approved articles whose scheduled_for time has passed
    and post them to LinkedIn. Called by the GitHub Actions 8am job.
    """
    if not LINKEDIN_ACCESS_TOKEN:
        print("⚠️  LINKEDIN_ACCESS_TOKEN not set — skipping LinkedIn post")
        return

    now = datetime.utcnow()
    approved = load_queue(status_filter="approved")

    if not approved:
        print("📭 No approved LinkedIn posts ready.")
        return

    for entry in approved:
        if not entry.scheduled_for:
            continue
        scheduled = datetime.fromisoformat(entry.scheduled_for)
        if now < scheduled:
            print(f"  ⏳ {entry.slug} scheduled for {entry.scheduled_for} — not yet")
            continue

        print(f"  🚀 Posting to LinkedIn: {entry.title}")
        success = _post_to_linkedin(entry.post_draft, entry.article_url)

        if success:
            update_queue_entry(
                entry.slug,
                status="posted",
                posted_at=datetime.utcnow().isoformat(),
            )
            print(f"  ✅ Posted: {entry.title}")
        else:
            print(f"  ❌ Failed to post: {entry.title}")


def _post_to_linkedin(post_text: str, article_url: str) -> bool:
    """Make the LinkedIn Share API call."""
    # Use org URN if posting as company page, else personal
    author_urn = LINKEDIN_PERSON_URN
    if not author_urn:
        print("  ❌ No LinkedIn URN configured (LINKEDIN_ORG_URN or LINKEDIN_PERSON_URN)")
        return False

    payload = {
        "author": author_urn,
        "commentary": post_text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "article": {
                "source": article_url,
                "title": "",
                "description": "",
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    try:
        response = httpx.post(
            "https://api.linkedin.com/rest/posts",
            headers={
                "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "LinkedIn-Version": "202401",
            },
            json=payload,
            timeout=30,
        )
        if response.status_code in (200, 201):
            return True
        else:
            print(f"  LinkedIn API error {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  LinkedIn post exception: {e}")
        return False


# ── SCHEDULING HELPERS ────────────────────────────────────────────────────────

def _next_weekday_8am_ct() -> datetime:
    """Return the next weekday at 8:00 AM CT (UTC-5 standard / UTC-6 daylight).
    We use UTC-5 (CST) as a safe approximation year-round."""
    CT_OFFSET_HOURS = 5  # UTC-5 (CST) — consistent, avoids DST complexity
    now_ct = datetime.utcnow() - timedelta(hours=CT_OFFSET_HOURS)

    # Start from tomorrow
    candidate = now_ct.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Skip weekends (Monday=0 ... Sunday=6)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)

    # Convert back to UTC for storage
    return candidate + timedelta(hours=CT_OFFSET_HOURS)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "post":
            post_approved_articles()
        elif cmd == "approve" and len(sys.argv) > 2:
            approve_article(sys.argv[2])
        elif cmd == "reject" and len(sys.argv) > 2:
            reject_article(sys.argv[2])
        elif cmd == "list":
            for e in load_queue():
                print(f"  [{e.status:8}] {e.slug}")