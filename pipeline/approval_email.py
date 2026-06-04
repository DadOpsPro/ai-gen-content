"""
pipeline/approval_email.py
──────────────────────────
Sends a Speechify-friendly HTML review email for each pending LinkedIn post.

The email contains:
  • Article title and full excerpt (listenable)
  • LinkedIn post draft (listenable)
  • One-click Approve and Skip buttons (trigger GitHub Actions workflow_dispatch)

Approval flow:
  1. This email is sent after each daily pipeline run
  2. Chris listens via Speechify / screen reader
  3. Clicks Approve → hits approve URL → triggers github_actions workflow
  4. GitHub Actions runs linkedin.py approve <slug> and commits updated queue
  5. The 8am CT LinkedIn poster job picks it up next morning

Email is sent via SMTP (uses Gmail / Google Workspace — chris@aidevdefense.com).
Set SMTP_PASSWORD to a Gmail App Password in GitHub Secrets.
"""

import os
import sys
import json
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import SITE_NAME, SITE_URL
from pipeline.linkedin import LinkedInQueueEntry

# ── CONFIG ────────────────────────────────────────────────────────────────────

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "chris@aidevdefense.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
REVIEW_EMAIL  = os.getenv("REVIEW_EMAIL", "chris@aidevdefense.com")

# GitHub repo details for workflow_dispatch approval trigger
GITHUB_REPO          = os.getenv("GITHUB_REPO", "DadOpsPro/ai-gen-content")
APPROVE_TOKEN = os.getenv("APPROVE_TOKEN", "")  # Fine-grained PAT with Actions:write


# ── APPROVAL URL ──────────────────────────────────────────────────────────────

def _approval_url(slug: str, action: str) -> str:
    """
    Build a URL that triggers the linkedin-approve GitHub Actions workflow.
    action = 'approve' | 'reject'
    """
    # We use a simple HTTPS endpoint: a GitHub Actions workflow_dispatch
    # triggered via GitHub's API. The URL encodes the slug and action as inputs.
    base = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/linkedin-approve.yml/dispatches"
    # We can't trigger via a GET link directly — instead we use a redirect service
    # hosted inside the repo's own GitHub Pages site. See site/approve.html.
    # Format: https://aidevdefense.com/approve.html?slug=SLUG&action=ACTION&token=TOKEN
    params = urllib.parse.urlencode({
        "slug":   slug,
        "action": action,
        "token":  APPROVE_TOKEN[:8] + "..." if APPROVE_TOKEN else "NOT_SET",
    })
    return f"{SITE_URL}/approve.html?{params}"


# ── EMAIL HTML TEMPLATE ───────────────────────────────────────────────────────

def _build_email_html(entries: List[LinkedInQueueEntry]) -> str:
    """
    Build a clean, screen-reader and Speechify friendly HTML email.
    Large font, generous spacing, clear structure.
    """
    articles_html = ""
    for i, entry in enumerate(entries, 1):
        approve_url = _approval_url(entry.slug, "approve")
        reject_url  = _approval_url(entry.slug, "reject")

        articles_html += f"""
        <article style="
            background:#f8fafc;
            border-left:4px solid #00c896;
            border-radius:8px;
            padding:28px 32px;
            margin-bottom:40px;
        ">
            <p style="
                font-size:13px;
                color:#6b7280;
                text-transform:uppercase;
                letter-spacing:0.08em;
                margin:0 0 8px 0;
            ">Article {i} of {len(entries)}</p>

            <h2 style="
                font-size:24px;
                font-weight:700;
                color:#0a0f1e;
                margin:0 0 16px 0;
                line-height:1.3;
            ">{entry.title}</h2>

            <p style="
                font-size:13px;
                color:#6b7280;
                margin:0 0 20px 0;
            ">
                Published at:
                <a href="{entry.article_url}" style="color:#00c896;">{entry.article_url}</a>
            </p>

            <h3 style="
                font-size:16px;
                font-weight:600;
                color:#374151;
                margin:0 0 10px 0;
                text-transform:uppercase;
                letter-spacing:0.05em;
            ">Article Summary</h3>

            <p style="
                font-size:17px;
                line-height:1.75;
                color:#1f2937;
                margin:0 0 28px 0;
            ">{entry.excerpt}</p>

            <h3 style="
                font-size:16px;
                font-weight:600;
                color:#374151;
                margin:0 0 10px 0;
                text-transform:uppercase;
                letter-spacing:0.05em;
            ">Proposed LinkedIn Post</h3>

            <div style="
                background:#ffffff;
                border:1px solid #e5e7eb;
                border-radius:6px;
                padding:20px 24px;
                font-size:17px;
                line-height:1.8;
                color:#1f2937;
                white-space:pre-wrap;
                margin-bottom:28px;
            ">{entry.post_draft}</div>

            <table cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
                <tr>
                    <td style="padding-right:12px;">
                        <a href="{approve_url}"
                           style="
                               display:inline-block;
                               background:#00c896;
                               color:#ffffff;
                               font-size:16px;
                               font-weight:700;
                               text-decoration:none;
                               padding:14px 32px;
                               border-radius:6px;
                           ">
                           ✅ Approve &amp; Schedule
                        </a>
                    </td>
                    <td>
                        <a href="{reject_url}"
                           style="
                               display:inline-block;
                               background:#ffffff;
                               color:#6b7280;
                               font-size:16px;
                               font-weight:600;
                               text-decoration:none;
                               padding:14px 32px;
                               border-radius:6px;
                               border:1px solid #d1d5db;
                           ">
                           ⏭ Skip This One
                        </a>
                    </td>
                </tr>
            </table>

            <p style="font-size:13px;color:#9ca3af;margin:10px 0 0 0;">
                If approved, this post will go out next weekday at 8:00 AM CT.
            </p>
        </article>
        """

    date_str = datetime.now().strftime("%A, %B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{SITE_NAME} — LinkedIn Review: {date_str}</title>
</head>
<body style="
    margin:0;
    padding:0;
    background:#f1f5f9;
    font-family: Georgia, 'Times New Roman', serif;
">
    <div style="
        max-width:680px;
        margin:0 auto;
        background:#ffffff;
    ">

        <!-- Header -->
        <div style="
            background:#0a0f1e;
            padding:32px 40px;
        ">
            <p style="
                color:#00c896;
                font-size:13px;
                font-weight:700;
                text-transform:uppercase;
                letter-spacing:0.1em;
                margin:0 0 6px 0;
            ">{SITE_NAME}</p>
            <h1 style="
                color:#ffffff;
                font-size:26px;
                font-weight:700;
                margin:0 0 6px 0;
                line-height:1.3;
            ">LinkedIn Post Review</h1>
            <p style="
                color:#94a3b8;
                font-size:15px;
                margin:0;
            ">{date_str} &nbsp;·&nbsp; {len(entries)} article{'s' if len(entries) != 1 else ''} ready for review</p>
        </div>

        <!-- Intro paragraph — Speechify reads this first -->
        <div style="padding:32px 40px 8px 40px;">
            <p style="
                font-size:17px;
                line-height:1.75;
                color:#374151;
                margin:0;
            ">
                Hello Chris. Your AI Dev Defense content pipeline has generated
                {'a new article' if len(entries) == 1 else str(len(entries)) + ' new articles'} today.
                Below {'is a summary and the proposed LinkedIn post' if len(entries) == 1 else 'are summaries and proposed LinkedIn posts'}.
                You can listen to the summaries using Speechify or your screen reader,
                then tap Approve to schedule the post for tomorrow morning at 8 AM Central Time,
                or Skip to pass on it.
            </p>
        </div>

        <!-- Articles -->
        <div style="padding:24px 40px 40px 40px;">
            {articles_html}
        </div>

        <!-- Footer -->
        <div style="
            background:#f8fafc;
            border-top:1px solid #e5e7eb;
            padding:24px 40px;
        ">
            <p style="
                font-size:13px;
                color:#9ca3af;
                margin:0;
                line-height:1.6;
            ">
                This email was sent automatically by the {SITE_NAME} content pipeline.<br>
                Posts not approved within 48 hours will remain pending until your next review.
            </p>
        </div>

    </div>
</body>
</html>"""


# ── PLAIN TEXT FALLBACK (extra Speechify friendly) ────────────────────────────

def _build_email_text(entries: List[LinkedInQueueEntry]) -> str:
    """Plain text version — clean fallback for screen readers."""
    lines = [
        f"{SITE_NAME} — LinkedIn Post Review",
        f"{datetime.now().strftime('%A, %B %d, %Y')}",
        f"{len(entries)} article(s) ready for review.",
        "",
        "Hello Chris. Your content pipeline has new articles ready for LinkedIn review.",
        "Read or listen to each summary and post draft below, then use the approve or skip links.",
        "",
        "=" * 60,
    ]

    for i, entry in enumerate(entries, 1):
        approve_url = _approval_url(entry.slug, "approve")
        reject_url  = _approval_url(entry.slug, "reject")
        lines += [
            "",
            f"ARTICLE {i} OF {len(entries)}",
            f"Title: {entry.title}",
            f"URL: {entry.article_url}",
            "",
            "SUMMARY:",
            entry.excerpt,
            "",
            "PROPOSED LINKEDIN POST:",
            entry.post_draft,
            "",
            f"APPROVE AND SCHEDULE: {approve_url}",
            f"SKIP THIS ONE: {reject_url}",
            "",
            "If approved, this post goes out next weekday at 8:00 AM Central Time.",
            "-" * 60,
        ]

    return "\n".join(lines)


# ── SEND ──────────────────────────────────────────────────────────────────────

def send_review_email(entries: List[LinkedInQueueEntry]) -> bool:
    """Send the review email for a list of pending queue entries."""
    if not entries:
        print("  📭 No pending LinkedIn posts — skipping review email")
        return True

    if not SMTP_PASSWORD:
        print("  ⚠️  SMTP_PASSWORD not set — cannot send review email")
        print("  💡 Set SMTP_PASSWORD in GitHub Secrets (Gmail App Password)")
        return False

    subject = (
        f"{SITE_NAME} — LinkedIn Review: "
        f"{entries[0].title[:50]}{'...' if len(entries[0].title) > 50 else ''}"
        if len(entries) == 1
        else f"{SITE_NAME} — LinkedIn Review: {len(entries)} articles ({datetime.now().strftime('%b %d')})"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = REVIEW_EMAIL

    msg.attach(MIMEText(_build_email_text(entries), "plain"))
    msg.attach(MIMEText(_build_email_html(entries), "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, REVIEW_EMAIL, msg.as_string())
        print(f"  ✅ Review email sent to {REVIEW_EMAIL} ({len(entries)} article(s))")
        return True
    except Exception as e:
        print(f"  ❌ Failed to send review email: {e}")
        return False