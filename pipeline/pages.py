"""
pipeline/pages.py
─────────────────
Generates static pages:
  - About page
  - Privacy Policy
  - Affiliate Disclosure
  - 404 page
"""

import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import SITE_NAME, SITE_URL, AUTHOR_NAME, OUTPUT_DIR

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {site_name}</title>
  <meta name="description" content="{meta_description}">
  <link rel="canonical" href="{site_url}/{slug}.html">
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <style>
    :root {{
      --font-sans: 'Georgia', serif;
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
    .site-header a {{ color: #00c896; text-decoration: none; font-weight: bold;
                      font-size: 1.2rem; }}
    .site-header nav {{ margin-left: auto; display: flex; gap: 1.5rem; }}
    .site-header nav a {{ font-size: 0.9rem; font-weight: normal; opacity: 0.8; }}
    .site-header nav a:hover {{ opacity: 1; }}
    .page-container {{ max-width: var(--max-width); margin: 0 auto; padding: 3rem 1.5rem; }}
    .page-hero {{ background: #f4f7ff; border-radius: 12px; padding: 2.5rem;
                  margin-bottom: 3rem; border-left: 4px solid var(--color-accent); }}
    .page-hero h1 {{ font-size: clamp(1.6rem, 4vw, 2.2rem); color: #0a0f1e;
                     margin-bottom: 0.75rem; }}
    .page-hero p {{ color: var(--color-muted); font-size: 1.05rem; }}
    h2 {{ font-size: 1.4rem; margin: 2.5rem 0 1rem; color: #0a0f1e;
          padding-bottom: 0.5rem; border-bottom: 2px solid #f0f0f0; }}
    h3 {{ font-size: 1.1rem; margin: 1.5rem 0 0.5rem; color: #0a0f1e; }}
    p {{ margin-bottom: 1.25rem; }}
    ul {{ margin: 0.75rem 0 1.5rem 1.5rem; }}
    li {{ margin-bottom: 0.5rem; }}
    a {{ color: var(--color-accent); }}
    .contact-card {{ background: #0a0f1e; color: #fff; border-radius: 12px;
                     padding: 2rem; margin: 2rem 0; text-align: center; }}
    .contact-card h3 {{ color: #00c896; margin-bottom: 0.75rem; }}
    .contact-card a {{ color: #00c896; font-weight: bold; }}
    .team-card {{ display: flex; gap: 1.5rem; align-items: flex-start;
                  background: #f9f9f9; border-radius: 12px; padding: 1.5rem;
                  margin: 1.5rem 0; }}
    .team-avatar {{ width: 72px; height: 72px; border-radius: 50%;
                    background: #0a0f1e; display: flex; align-items: center;
                    justify-content: center; flex-shrink: 0; }}
    .team-avatar span {{ color: #00c896; font-weight: 700; font-size: 1.5rem;
                         font-family: sans-serif; }}
    .team-info h3 {{ margin: 0 0 0.4rem; }}
    .team-info p {{ margin: 0; color: var(--color-muted); font-size: 0.95rem; }}
    .highlight-box {{ background: #f0fdf8; border: 1px solid #00c896;
                      border-radius: 8px; padding: 1.25rem 1.5rem; margin: 1.5rem 0; }}
    .last-updated {{ color: var(--color-muted); font-size: 0.85rem;
                     margin-top: 3rem; padding-top: 1rem;
                     border-top: 1px solid #eee; }}
    footer {{ background: #0a0f1e; color: #888; text-align: center;
              padding: 2rem; margin-top: 4rem; font-size: 0.85rem; }}
    footer a {{ color: #888; }}
  </style>
</head>
<body>
  <header class="site-header">
    <a href="/">{site_name}</a>
    <nav>
      <a href="/">Home</a>
      <a href="/about.html">About</a>
      <a href="/privacy.html">Privacy</a>
    </nav>
  </header>
  <main class="page-container">
    {content}
    <p class="last-updated">Last updated: {last_updated}</p>
  </main>
  <footer>
    <p>&copy; {year} {site_name} &middot;
    <a href="/privacy.html">Privacy Policy</a> &middot;
    <a href="/affiliate-disclosure.html">Affiliate Disclosure</a> &middot;
    <a href="/about.html">About</a></p>
  </footer>
</body>
</html>"""


def build_about_page(output_dir: str = OUTPUT_DIR) -> str:
    """Generate the About page."""
    content = f"""
    <div class="page-hero">
      <h1>About AI Dev Defense</h1>
      <p>Independent research and analysis on AI-powered software testing
         and application security — written for engineers, by engineers.</p>
    </div>

    <h2>What We Do</h2>
    <p>AI Dev Defense covers the rapidly evolving intersection of artificial
       intelligence with software quality and security. We publish in-depth
       tool reviews, practical how-to guides, weekly trend roundups, and
       deep-dive analyses to help software engineers and security professionals
       navigate an increasingly AI-driven landscape.</p>

    <p>Our content focuses on three core areas:</p>
    <ul>
      <li><strong>AI Test Automation</strong> — tools, frameworks, and strategies
          for using AI to write, run, and maintain tests</li>
      <li><strong>AI Application Security</strong> — how AI is changing threat
          detection, vulnerability scanning, and secure code review</li>
      <li><strong>Developer Tooling</strong> — reviews and comparisons of the
          AI-powered tools reshaping how software gets built and shipped</li>
    </ul>

    <div class="highlight-box">
      <strong>Our editorial standard:</strong> Every tool we review is evaluated
      on real-world criteria. We call out limitations as clearly as we highlight
      strengths. Our goal is to save you time, not sell you something.
    </div>

    <h2>Who's Behind This</h2>
    <div class="team-card">
      <div class="team-avatar"><span>C</span></div>
      <div class="team-info">
        <h3>{AUTHOR_NAME}</h3>
        <p>Founder & Editor, {SITE_NAME}</p>
        <p style="margin-top:.5rem">Software professional with a focus on
           development operations, AI tooling, and building systems that scale.
           Started {SITE_NAME} to cut through the noise in an industry moving
           faster than most teams can track.</p>
      </div>
    </div>

    <h2>Why We Started This</h2>
    <p>The AI tooling space moves fast — new testing frameworks, security
       scanners, and code review tools launch every week. Most coverage is
       either surface-level marketing or buried in academic papers. There
       wasn't a reliable, independent source covering this intersection
       practically for working engineers.</p>
    <p>That's the gap {SITE_NAME} fills.</p>

    <h2>Editorial Independence</h2>
    <p>We maintain strict editorial independence. Tool vendors do not pay
       for reviews or editorial coverage. When we recommend a product, it's
       because we believe it genuinely helps our readers — not because of a
       commercial relationship.</p>
    <p>Some articles contain affiliate links, which means we earn a small
       commission if you purchase through them, at no extra cost to you.
       This is disclosed clearly in every article and never influences our
       editorial judgment. See our full
       <a href="/affiliate-disclosure.html">Affiliate Disclosure</a>.</p>

    <h2>Stay in the Loop</h2>
    <p>The best way to follow our work is via the weekly newsletter — a
       curated digest of the week's most important developments in AI testing
       and security, delivered every Monday.</p>

    <div class="contact-card">
      <h3>Get in Touch</h3>
      <p>Questions, feedback, or partnership inquiries:</p>
      <a href="mailto:chris@aidevdefense.com">chris@aidevdefense.com</a>
      <p style="margin-top:1rem;opacity:.7;font-size:.85rem">
        We read every email and respond to most within 2 business days.
      </p>
    </div>
    """

    html = PAGE_TEMPLATE.format(
        title="About",
        site_name=SITE_NAME,
        meta_description=f"Learn about {SITE_NAME} — independent AI testing and application security research for software engineers.",
        site_url=SITE_URL,
        slug="about",
        content=content,
        last_updated=datetime.now().strftime("%B %d, %Y"),
        year=datetime.now().year,
    )

    path = Path(output_dir) / "about.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print("  ✅ About page generated")
    return str(path)


def build_privacy_page(output_dir: str = OUTPUT_DIR) -> str:
    """Generate the Privacy Policy page."""
    content = f"""
    <div class="page-hero">
      <h1>Privacy Policy</h1>
      <p>How {SITE_NAME} collects, uses, and protects your information.</p>
    </div>

    <p>This Privacy Policy describes how {SITE_NAME} ("we", "us", or "our"),
       operating at <a href="{SITE_URL}">{SITE_URL}</a>, collects and uses
       information when you visit our website.</p>

    <h2>Information We Collect</h2>

    <h3>Information You Provide</h3>
    <p>We collect information you voluntarily provide, including:</p>
    <ul>
      <li>Email address when you subscribe to our newsletter</li>
      <li>Name and email when you contact us directly</li>
    </ul>

    <h3>Automatically Collected Information</h3>
    <p>When you visit our site, certain information is collected automatically:</p>
    <ul>
      <li><strong>Log data</strong> — IP address, browser type, pages visited,
          time and date of visit, referring URL</li>
      <li><strong>Cookies</strong> — small data files placed on your device
          by our advertising and analytics partners (see below)</li>
    </ul>

    <h2>How We Use Your Information</h2>
    <ul>
      <li>To send the newsletter you subscribed to (you can unsubscribe at any time)</li>
      <li>To respond to your emails and inquiries</li>
      <li>To understand how our content is used and improve the site</li>
      <li>To serve relevant advertisements through Google AdSense</li>
    </ul>

    <h2>Google AdSense & Advertising</h2>
    <p>We use Google AdSense to display advertisements. Google uses cookies
       to serve ads based on your prior visits to this and other websites.
       You may opt out of personalized advertising by visiting
       <a href="https://www.google.com/settings/ads" target="_blank"
          rel="noopener">Google Ads Settings</a>.</p>
    <p>Google's use of advertising cookies enables it and its partners to
       serve ads based on your visit to our site and other sites on the
       internet. For more information, see
       <a href="https://policies.google.com/technologies/ads" target="_blank"
          rel="noopener">Google's advertising policy</a>.</p>

    <h2>Affiliate Links</h2>
    <p>Some links on this site are affiliate links. If you click and make a
       purchase, we may earn a commission at no additional cost to you.
       See our <a href="/affiliate-disclosure.html">Affiliate Disclosure</a>
       for full details.</p>

    <h2>Third-Party Services</h2>
    <p>We use the following third-party services that may collect data:</p>
    <ul>
      <li><strong>Google Analytics</strong> — website traffic analysis
          (<a href="https://policies.google.com/privacy" target="_blank"
              rel="noopener">Privacy Policy</a>)</li>
      <li><strong>Google AdSense</strong> — advertising
          (<a href="https://policies.google.com/privacy" target="_blank"
              rel="noopener">Privacy Policy</a>)</li>
      <li><strong>Mailchimp</strong> — newsletter delivery
          (<a href="https://mailchimp.com/legal/privacy/" target="_blank"
              rel="noopener">Privacy Policy</a>)</li>
    </ul>

    <h2>Cookies</h2>
    <p>Our site uses cookies for advertising and analytics. You can control
       cookies through your browser settings. Disabling cookies may affect
       some site functionality. By continuing to use our site, you consent
       to our use of cookies in accordance with this policy.</p>

    <h2>Data Retention</h2>
    <p>We retain your email address for as long as you are subscribed to
       our newsletter. You can unsubscribe at any time using the link in
       any newsletter email. Contact us to request deletion of your data.</p>

    <h2>Children's Privacy</h2>
    <p>Our site is not directed at children under 13. We do not knowingly
       collect personal information from children under 13.</p>

    <h2>Your Rights</h2>
    <p>Depending on your location, you may have rights including:</p>
    <ul>
      <li>Access to the personal data we hold about you</li>
      <li>Correction of inaccurate data</li>
      <li>Deletion of your data</li>
      <li>Objection to processing of your data</li>
    </ul>
    <p>To exercise these rights, contact us at
       <a href="mailto:chris@aidevdefense.com">chris@aidevdefense.com</a>.</p>

    <h2>Changes to This Policy</h2>
    <p>We may update this Privacy Policy from time to time. We will post
       any changes on this page with an updated date. Continued use of
       the site after changes constitutes acceptance of the new policy.</p>

    <h2>Contact Us</h2>
    <div class="contact-card">
      <h3>Privacy Questions</h3>
      <p>For any privacy-related questions or requests:</p>
      <a href="mailto:chris@aidevdefense.com">chris@aidevdefense.com</a>
    </div>
    """

    html = PAGE_TEMPLATE.format(
        title="Privacy Policy",
        site_name=SITE_NAME,
        meta_description=f"{SITE_NAME} Privacy Policy — how we collect, use, and protect your information.",
        site_url=SITE_URL,
        slug="privacy",
        content=content,
        last_updated=datetime.now().strftime("%B %d, %Y"),
        year=datetime.now().year,
    )

    path = Path(output_dir) / "privacy.html"
    path.write_text(html, encoding="utf-8")
    print("  ✅ Privacy Policy generated")
    return str(path)


def build_affiliate_disclosure_page(output_dir: str = OUTPUT_DIR) -> str:
    """Generate the Affiliate Disclosure page."""
    content = f"""
    <div class="page-hero">
      <h1>Affiliate Disclosure</h1>
      <p>Transparency about how {SITE_NAME} earns revenue.</p>
    </div>

    <div class="highlight-box">
      <strong>Plain English summary:</strong> Some links on this site earn us
      a small commission if you buy. It never costs you extra, and it never
      changes what we recommend.
    </div>

    <h2>FTC Disclosure</h2>
    <p>In accordance with the Federal Trade Commission's guidelines,
       {SITE_NAME} discloses that some links on this website are affiliate
       links. This means that if you click on a link and make a purchase,
       we may receive a commission from the sale.</p>

    <h2>Our Affiliate Relationships</h2>
    <p>We participate in affiliate programs including but not limited to:</p>
    <ul>
      <li><strong>Amazon Associates</strong> — as an Amazon Associate we
          earn from qualifying purchases</li>
      <li><strong>Software tool affiliate programs</strong> — various developer
          tools and SaaS products we review and recommend</li>
    </ul>

    <h2>Our Editorial Promise</h2>
    <p>Affiliate relationships do not influence our editorial content.
       We only recommend tools and products we believe genuinely help
       our readers. We will always tell you about limitations and
       downsides, not just strengths.</p>
    <p>We do not accept payment for positive reviews. Vendors cannot
       pay to be featured or reviewed favorably.</p>

    <h2>Identifying Affiliate Links</h2>
    <p>Affiliate links on this site are marked with the
       <code>rel="nofollow"</code> attribute. We also include a disclosure
       notice at the top of articles that contain affiliate links.</p>

    <h2>Questions</h2>
    <p>If you have questions about our affiliate relationships or editorial
       policies, contact us at
       <a href="mailto:chris@aidevdefense.com">chris@aidevdefense.com</a>.</p>
    """

    html = PAGE_TEMPLATE.format(
        title="Affiliate Disclosure",
        site_name=SITE_NAME,
        meta_description=f"{SITE_NAME} affiliate disclosure — transparency about how we earn revenue.",
        site_url=SITE_URL,
        slug="affiliate-disclosure",
        content=content,
        last_updated=datetime.now().strftime("%B %d, %Y"),
        year=datetime.now().year,
    )

    path = Path(output_dir) / "affiliate-disclosure.html"
    path.write_text(html, encoding="utf-8")
    print("  ✅ Affiliate Disclosure generated")
    return str(path)


def build_404_page(output_dir: str = OUTPUT_DIR) -> str:
    """Generate a custom 404 page."""
    content = f"""
    <div style="text-align:center;padding:4rem 0">
      <div style="font-size:5rem;margin-bottom:1rem">🔍</div>
      <h1 style="font-size:2rem;margin-bottom:1rem">Page Not Found</h1>
      <p style="color:#666;margin-bottom:2rem">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <a href="/" style="background:#0a0f1e;color:#00c896;padding:.75rem 2rem;
         border-radius:8px;text-decoration:none;font-weight:bold;font-family:sans-serif">
        ← Back to Home
      </a>
    </div>
    """

    html = PAGE_TEMPLATE.format(
        title="Page Not Found",
        site_name=SITE_NAME,
        meta_description=f"Page not found — {SITE_NAME}",
        site_url=SITE_URL,
        slug="404",
        content=content,
        last_updated=datetime.now().strftime("%B %d, %Y"),
        year=datetime.now().year,
    )

    path = Path(output_dir) / "404.html"
    path.write_text(html, encoding="utf-8")
    print("  ✅ 404 page generated")
    return str(path)


def build_all_pages(output_dir: str = OUTPUT_DIR):
    """Build all static pages."""
    print("\n📄 Building static pages...")
    build_about_page(output_dir)
    build_privacy_page(output_dir)
    build_affiliate_disclosure_page(output_dir)
    build_404_page(output_dir)
    print("✅ All pages built")


if __name__ == "__main__":
    build_all_pages()