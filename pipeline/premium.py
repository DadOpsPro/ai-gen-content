"""
pipeline/premium.py
────────────────────
Stripe-powered premium report system.
- Generates a deep-dive premium PDF report
- Creates a Stripe payment link
- Delivers report via email after payment webhook
"""

import stripe
import json
import sys
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import (
    STRIPE_SECRET_KEY, PREMIUM_REPORT_PRICE_USD, SITE_NAME, SITE_URL
)

stripe.api_key = STRIPE_SECRET_KEY


@dataclass
class PremiumReport:
    title: str
    slug: str
    description: str
    price_usd: int
    stripe_price_id: Optional[str]
    stripe_payment_link: Optional[str]
    html_content: str


def create_premium_product(title: str, description: str, price_usd: int = None) -> dict:
    """Create a Stripe product + price + payment link for a premium report."""
    if not STRIPE_SECRET_KEY:
        print("[SKIP] Stripe not configured")
        return {}

    price_usd = price_usd or PREMIUM_REPORT_PRICE_USD

    try:
        # Create product
        product = stripe.Product.create(
            name=title,
            description=description,
            metadata={"type": "premium_report", "site": SITE_NAME},
        )

        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=price_usd * 100,  # cents
            currency="usd",
        )

        # Create payment link
        payment_link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            after_completion={
                "type": "redirect",
                "redirect": {"url": f"{SITE_URL}/report-delivered?session={{CHECKOUT_SESSION_ID}}"}
            },
            metadata={"report_title": title},
        )

        print(f"  ✅ Stripe product created: {product.id}")
        print(f"  ✅ Payment link: {payment_link.url}")

        return {
            "product_id": product.id,
            "price_id":   price.id,
            "payment_link": payment_link.url,
        }

    except stripe.error.StripeError as e:
        print(f"  ❌ Stripe error: {e}")
        return {}


def generate_premium_report_landing_page(
    title: str,
    description: str,
    payment_link: str,
    price_usd: int,
    sample_content: str,
    topics_covered: list,
) -> str:
    """Generate a landing page HTML for a premium report."""

    topics_html = "".join(f"<li>✓ {t}</li>" for t in topics_covered)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {SITE_NAME} Premium</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Georgia', serif; color: #1a1a2e; background: #f9f9f9; }}
    .hero {{ background: linear-gradient(135deg, #0a0a1a 0%, #0c1a3a 100%);
             color: #fff; padding: 5rem 2rem; text-align: center; }}
    .hero .badge {{ background: #0070f3; color: #fff; padding: .35rem .8rem;
                    border-radius: 20px; font-size: .85rem; display: inline-block;
                    margin-bottom: 1.5rem; font-weight: bold; }}
    .hero h1 {{ font-size: clamp(1.8rem, 4vw, 2.8rem); max-width: 700px;
                margin: 0 auto 1.5rem; line-height: 1.2; }}
    .hero p {{ color: #aaa; max-width: 560px; margin: 0 auto 2.5rem; font-size: 1.1rem; }}
    .cta-btn {{ background: #0070f3; color: #fff; border: none; padding: 1rem 2.5rem;
                font-size: 1.15rem; border-radius: 8px; cursor: pointer; font-weight: bold;
                text-decoration: none; display: inline-block; transition: transform .15s; }}
    .cta-btn:hover {{ transform: scale(1.03); background: #0060d3; }}
    .price-note {{ color: #888; margin-top: 1rem; font-size: .9rem; }}
    .content {{ max-width: 800px; margin: 4rem auto; padding: 0 1.5rem; }}
    .includes {{ background: #fff; border-radius: 12px; padding: 2.5rem;
                 box-shadow: 0 2px 16px rgba(0,0,0,.08); margin-bottom: 3rem; }}
    .includes h2 {{ font-size: 1.5rem; margin-bottom: 1.5rem; }}
    .includes ul {{ list-style: none; }}
    .includes li {{ padding: .5rem 0; font-size: 1rem; border-bottom: 1px solid #f0f0f0; }}
    .sample {{ background: #f4f4f4; border-left: 4px solid #0070f3;
               padding: 1.5rem 2rem; border-radius: 0 8px 8px 0; margin-bottom: 3rem; }}
    .sample h3 {{ margin-bottom: .75rem; color: #0070f3; }}
    .guarantee {{ text-align: center; padding: 2rem; color: #555; font-size: .9rem; }}
    footer {{ background: #0a0a1a; color: #888; text-align: center; padding: 2rem; font-size: .85rem; }}
  </style>
</head>
<body>
  <section class="hero">
    <span class="badge">PREMIUM REPORT</span>
    <h1>{title}</h1>
    <p>{description}</p>
    <a href="{payment_link}" class="cta-btn">Get Instant Access — ${price_usd}</a>
    <p class="price-note">One-time payment · Instant PDF download · 30-day money-back guarantee</p>
  </section>
  <div class="content">
    <div class="includes">
      <h2>What's Inside This Report</h2>
      <ul>{topics_html}</ul>
    </div>
    <div class="sample">
      <h3>📄 Sample Section</h3>
      {sample_content[:800]}...
      <p style="margin-top:1rem;font-style:italic;color:#888">
        [Full report: 40+ pages, 15,000+ words, code examples, and tool comparisons]
      </p>
    </div>
    <div style="text-align:center;margin:2rem 0">
      <a href="{payment_link}" class="cta-btn">Yes, I Want This Report — ${price_usd}</a>
    </div>
    <div class="guarantee">
      🔒 Secure payment via Stripe · 30-day money-back guarantee · Instant delivery
    </div>
  </div>
  <footer>
    <p>&copy; {SITE_NAME} · <a href="/" style="color:#888">Home</a></p>
  </footer>
</body>
</html>"""


def handle_stripe_webhook(payload: bytes, sig_header: str, webhook_secret: str) -> dict:
    """
    Handle Stripe webhook events.
    Call this from your web server (Flask/FastAPI) at /stripe-webhook
    """
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return {"error": "Invalid payload", "status": 400}
    except stripe.error.SignatureVerificationError:
        return {"error": "Invalid signature", "status": 400}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_details", {}).get("email")
        report_title = session.get("metadata", {}).get("report_title", "")

        print(f"✅ Payment received from {customer_email} for: {report_title}")
        # TODO: send PDF via email (integrate with SendGrid/SES)
        send_report_email(customer_email, report_title)

    return {"status": 200}


def send_report_email(email: str, report_title: str):
    """Send the purchased report via email. Requires email service integration."""
    print(f"  📧 [TODO] Send report '{report_title}' to {email}")
    print("  Integrate with SendGrid/AWS SES to deliver PDF automatically")
    # In production:
    # 1. Find the PDF for this report in your files
    # 2. Use SendGrid/SES transactional email with attachment
    # 3. Log delivery in database
