"""
pipeline/article_review_email.py
─────────────────────────────────
Sends Chris a Speechify-friendly HTML email with a draft article and
a text field for his personal take. When he submits, it triggers the
publish-approved GitHub Actions workflow with his input as a parameter.
"""

import json
import os
import smtplib
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import SITE_NAME

SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
REVIEW_EMAIL  = os.environ.get("REVIEW_EMAIL", "chris@aidevdefense.com")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "DadOpsPro/ai-gen-content")
APPROVE_TOKEN = os.environ.get("APPROVE_TOKEN", "")
SITE_URL      = os.environ.get("SITE_URL", "https://aidevdefense.com")


def _approval_page_url(slug: str, draft_b64: str) -> str:
    """URL to the article approval page with draft pre-loaded."""
    params = urllib.parse.urlencode({"slug": slug, "draft": draft_b64})
    return f"{SITE_URL}/article-approve.html?{params}"


def build_review_email_html(topic: str, article_type: str, draft_markdown: str, slug: str) -> str:
    """Build the Speechify-friendly HTML review email."""

    import base64
    draft_b64 = base64.urlsafe_b64encode(draft_markdown.encode()).decode()
    approve_url = _approval_page_url(slug, draft_b64)

    date_str = datetime.now().strftime("%A, %B %d, %Y")

    # Show a clean readable version of the draft for Speechify
    # Strip markdown symbols for easier listening
    readable = draft_markdown
    readable = readable.replace("## ", "").replace("### ", "").replace("**", "")
    readable = readable.replace("[CHRIS TAKE]", "— YOUR TAKE GOES HERE —")
    readable = readable.replace("[UNVERIFIED]", "(unverified — please check)")

    paragraphs = "".join(
        f'<p style="font-size:17px;line-height:1.85;color:#374151;margin:0 0 1.25rem 0;">{p.strip()}</p>'
        for p in readable.split("\n")
        if p.strip() and not p.strip().startswith("#")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{SITE_NAME} — Article Draft Review: {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Georgia,'Times New Roman',serif;">
<div style="max-width:680px;margin:0 auto;background:#ffffff;">

  <!-- Header -->
  <div style="background:#0a0f1e;padding:32px 40px;">
    <p style="color:#00c896;font-size:13px;font-weight:700;text-transform:uppercase;
              letter-spacing:0.1em;margin:0 0 6px 0;">{SITE_NAME}</p>
    <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0 0 6px 0;
               line-height:1.3;">Article Draft Ready for Review</h1>
    <p style="color:#94a3b8;font-size:15px;margin:0;">{date_str}</p>
  </div>

  <!-- Intro -->
  <div style="padding:32px 40px 16px 40px;">
    <p style="font-size:17px;line-height:1.75;color:#374151;margin:0 0 1rem 0;">
      Hello Chris. Your pipeline has drafted a new article for your review.
      Listen to the draft below using Speechify. When you are ready, tap
      <strong>Add My Take &amp; Publish</strong> to open the approval page,
      enter your personal perspective, and submit. The final article will
      publish automatically after you submit.
    </p>
    <p style="font-size:15px;color:#6b7280;margin:0;">
      Article type: <strong>{article_type.replace("_", " ").title()}</strong>
    </p>
  </div>

  <!-- Topic -->
  <div style="padding:0 40px 24px 40px;">
    <div style="background:#f8fafc;border-left:4px solid #00c896;padding:16px 20px;border-radius:4px;">
      <p style="font-size:13px;color:#6b7280;margin:0 0 4px 0;text-transform:uppercase;
                letter-spacing:0.08em;font-weight:700;">Topic</p>
      <p style="font-size:18px;font-weight:700;color:#0a0f1e;margin:0;">{topic}</p>
    </div>
  </div>

  <!-- Draft content (Speechify-friendly) -->
  <div style="padding:0 40px 32px 40px;">
    <p style="font-size:13px;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;
              font-weight:700;margin:0 0 16px 0;">Draft Article</p>
    {paragraphs}
  </div>

  <!-- CTA -->
  <div style="padding:0 40px 40px 40px;">
    <p style="font-size:16px;line-height:1.7;color:#374151;margin:0 0 24px 0;">
      The section marked <strong>YOUR TAKE GOES HERE</strong> is where your
      personal experience and opinion will be inserted. Tap below to open the
      approval page, type your take (a few sentences is plenty), and submit.
    </p>
    <table cellpadding="0" cellspacing="0">
      <tr>
        <td style="padding-right:12px;">
          <a href="{approve_url}"
             style="display:inline-block;background:#00c896;color:#ffffff;
                    font-size:16px;font-weight:700;text-decoration:none;
                    padding:14px 32px;border-radius:6px;">
            ✍️ Add My Take &amp; Publish
          </a>
        </td>
        <td>
          <a href="{SITE_URL}/article-approve.html?slug={slug}&action=skip"
             style="display:inline-block;background:#ffffff;color:#6b7280;
                    font-size:16px;font-weight:600;text-decoration:none;
                    padding:14px 32px;border-radius:6px;border:1px solid #d1d5db;">
            ⏭ Skip This One
          </a>
        </td>
      </tr>
    </table>
  </div>

  <!-- Footer -->
  <div style="background:#f8fafc;border-top:1px solid #e5e7eb;padding:24px 40px;">
    <p style="font-size:13px;color:#9ca3af;margin:0;line-height:1.6;">
      This draft was generated by the {SITE_NAME} content pipeline.<br>
      Drafts not reviewed within 48 hours will expire and be regenerated on the next run.
    </p>
  </div>

</div>
</body>
</html>"""


def send_draft_review_email(topic: str, article_type: str, draft_markdown: str, slug: str) -> bool:
    """Send the draft review email to Chris."""
    if not all([SMTP_USER, SMTP_PASSWORD, REVIEW_EMAIL]):
        print("  [WARN] SMTP credentials not set — skipping draft review email")
        return False

    html_body = build_review_email_html(topic, article_type, draft_markdown, slug)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[AI Dev Defense] Draft Ready: {topic[:60]}"
    msg["From"]    = SMTP_USER
    msg["To"]      = REVIEW_EMAIL

    plain = (
        f"AI Dev Defense — Article Draft Review\n"
        f"{datetime.now().strftime('%A, %B %d, %Y')}\n\n"
        f"Topic: {topic}\n"
        f"Type: {article_type}\n\n"
        f"Draft:\n{draft_markdown}\n\n"
        f"To add your take and publish, visit:\n"
        f"{_approval_page_url(slug, '')}\n"
    )

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, REVIEW_EMAIL, msg.as_string())
        print(f"  📧 Draft review email sent to {REVIEW_EMAIL}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to send draft review email: {e}")
        return False
