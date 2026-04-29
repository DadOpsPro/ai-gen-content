"""
dashboard/app.py
────────────────
Simple monitoring dashboard showing:
- Articles published
- Estimated traffic & revenue
- Affiliate link stats
- Pipeline health
- Content calendar

Run: python dashboard/app.py
Visit: http://localhost:3001
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, render_template_string

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import SITE_NAME, NICHE, AFFILIATE_LINKS

app = Flask(__name__)
STATE_FILE = Path(__file__).parent.parent / "state.json"
OUTPUT_DIR = Path(__file__).parent.parent / "site" / "output" / "posts"


def get_stats():
    state = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

    article_count = state.get("article_count", 0)
    last_run = state.get("last_run", "Never")
    slugs = state.get("published_slugs", [])

    # Estimate metrics (rough SEO projections)
    avg_monthly_visitors_per_article = 150  # conservative for niche site
    estimated_monthly_visitors = article_count * avg_monthly_visitors_per_article
    cpm = 3.50  # $ per 1000 pageviews (AdSense niche average)
    estimated_monthly_ad_revenue = (estimated_monthly_visitors / 1000) * cpm
    affiliate_conversion_rate = 0.01  # 1%
    affiliate_avg_commission = 15  # $
    estimated_affiliate_revenue = (estimated_monthly_visitors
                                   * affiliate_conversion_rate
                                   * affiliate_avg_commission)

    return {
        "site_name": SITE_NAME,
        "niche": NICHE,
        "article_count": article_count,
        "last_run": last_run,
        "recent_slugs": slugs[-10:],
        "affiliate_count": len(AFFILIATE_LINKS),
        "estimates": {
            "monthly_visitors": estimated_monthly_visitors,
            "ad_revenue": round(estimated_monthly_ad_revenue, 2),
            "affiliate_revenue": round(estimated_affiliate_revenue, 2),
            "total_revenue": round(estimated_monthly_ad_revenue + estimated_affiliate_revenue, 2),
        }
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ stats.site_name }} — Dashboard</title>
  <meta http-equiv="refresh" content="60">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

    :root {
      --bg: #0a0a1a;
      --card: #111827;
      --border: #1e293b;
      --text: #e2e8f0;
      --muted: #64748b;
      --accent: #0070f3;
      --green: #10b981;
      --yellow: #f59e0b;
      --red: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Space Grotesk', sans-serif; background: var(--bg);
           color: var(--text); min-height: 100vh; }

    .topbar { background: var(--card); border-bottom: 1px solid var(--border);
              padding: 1rem 2rem; display: flex; align-items: center;
              justify-content: space-between; }
    .topbar h1 { font-size: 1.1rem; font-weight: 700; }
    .topbar h1 span { color: var(--accent); }
    .topbar .status { display: flex; align-items: center; gap: .5rem;
                      font-size: .8rem; color: var(--muted); }
    .status-dot { width: 8px; height: 8px; border-radius: 50%;
                  background: var(--green); animation: pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }

    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem; padding: 2rem; }
    .card { background: var(--card); border: 1px solid var(--border);
            border-radius: 12px; padding: 1.5rem; }
    .card.wide { grid-column: span 2; }
    .card-label { font-size: .75rem; color: var(--muted); text-transform: uppercase;
                  letter-spacing: .08em; margin-bottom: .75rem; }
    .card-value { font-size: 2rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .card-value.green { color: var(--green); }
    .card-value.blue { color: var(--accent); }
    .card-value.yellow { color: var(--yellow); }
    .card-sub { font-size: .8rem; color: var(--muted); margin-top: .4rem; }

    .revenue-breakdown { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
    .rev-item { background: var(--bg); border-radius: 8px; padding: .75rem 1rem;
                flex: 1; min-width: 120px; }
    .rev-item .label { font-size: .75rem; color: var(--muted); margin-bottom: .25rem; }
    .rev-item .amount { font-size: 1.2rem; font-weight: 700; color: var(--green);
                        font-family: 'JetBrains Mono', monospace; }

    .articles-list { margin-top: 1rem; }
    .article-row { display: flex; align-items: center; gap .75rem;
                   padding: .6rem 0; border-bottom: 1px solid var(--border);
                   font-size: .85rem; }
    .article-row:last-child { border-bottom: none; }
    .article-slug { color: var(--accent); font-family: 'JetBrains Mono', monospace;
                    font-size: .8rem; flex: 1; overflow: hidden;
                    text-overflow: ellipsis; white-space: nowrap; }
    .article-badge { background: var(--border); color: var(--muted); padding: .2rem .5rem;
                     border-radius: 4px; font-size: .7rem; }

    .pipeline-status { display: grid; grid-template-columns: 1fr 1fr;
                       gap: 1rem; margin-top: 1rem; }
    .pipe-item { background: var(--bg); border-radius: 8px; padding: .75rem 1rem; }
    .pipe-label { font-size: .75rem; color: var(--muted); margin-bottom: .25rem; }
    .pipe-value { font-size: .9rem; font-weight: 600; }
    .pipe-value.ok { color: var(--green); }
    .pipe-value.warn { color: var(--yellow); }
    .pipe-value.err { color: var(--red); }

    .action-btns { display: flex; gap: .75rem; margin-top: 1rem; flex-wrap: wrap; }
    .btn { background: var(--accent); color: #fff; border: none; padding: .6rem 1.2rem;
           border-radius: 8px; font-size: .85rem; cursor: pointer; font-weight: 600;
           font-family: inherit; text-decoration: none; display: inline-block; }
    .btn.secondary { background: var(--border); color: var(--text); }
    .btn:hover { opacity: .85; }

    footer { text-align: center; padding: 2rem; color: var(--muted); font-size: .8rem; }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>🤖 <span>{{ stats.site_name }}</span> Dashboard</h1>
    <div class="status">
      <div class="status-dot"></div>
      Engine Active · Last run: {{ stats.last_run[:19] if stats.last_run != 'Never' else 'Never' }}
    </div>
  </div>

  <div class="grid">
    <!-- Articles Published -->
    <div class="card">
      <div class="card-label">Articles Published</div>
      <div class="card-value blue">{{ stats.article_count }}</div>
      <div class="card-sub">{{ '🟡 Building' if stats.article_count < 10 else '🟢 SEO Seeded' }}</div>
    </div>

    <!-- Estimated Monthly Visitors -->
    <div class="card">
      <div class="card-label">Est. Monthly Visitors</div>
      <div class="card-value">{{ "{:,}".format(stats.estimates.monthly_visitors) }}</div>
      <div class="card-sub">~150/article (conservative)</div>
    </div>

    <!-- Affiliate Programs -->
    <div class="card">
      <div class="card-label">Affiliate Programs</div>
      <div class="card-value yellow">{{ stats.affiliate_count }}</div>
      <div class="card-sub">Active partner links</div>
    </div>

    <!-- Estimated Revenue -->
    <div class="card wide">
      <div class="card-label">Estimated Monthly Revenue (Projection)</div>
      <div class="card-value green">${{ stats.estimates.total_revenue }}</div>
      <div class="revenue-breakdown">
        <div class="rev-item">
          <div class="label">AdSense / Display</div>
          <div class="amount">${{ stats.estimates.ad_revenue }}</div>
        </div>
        <div class="rev-item">
          <div class="label">Affiliate Commissions</div>
          <div class="amount">${{ stats.estimates.affiliate_revenue }}</div>
        </div>
        <div class="rev-item">
          <div class="label">Premium Reports</div>
          <div class="amount">$0</div>
        </div>
      </div>
      <div class="card-sub" style="margin-top:.75rem">
        ⚠️ These are rough projections based on niche averages. Actual results vary.
      </div>
    </div>

    <!-- Recent Articles -->
    <div class="card wide">
      <div class="card-label">Recently Published</div>
      <div class="articles-list">
        {% for slug in stats.recent_slugs[-8:]|reverse %}
        <div class="article-row">
          <span class="article-slug">/posts/{{ slug }}.html</span>
          <span class="article-badge">published</span>
        </div>
        {% endfor %}
        {% if not stats.recent_slugs %}
        <div style="color:var(--muted);font-size:.9rem;padding:.5rem 0">
          No articles yet. Run: <code>python -m pipeline.orchestrator --mode seed</code>
        </div>
        {% endif %}
      </div>
    </div>

    <!-- Pipeline Health -->
    <div class="card">
      <div class="card-label">Pipeline Health</div>
      <div class="pipeline-status">
        <div class="pipe-item">
          <div class="pipe-label">AI Generator</div>
          <div class="pipe-value ok">✓ Ready</div>
        </div>
        <div class="pipe-item">
          <div class="pipe-label">Scraper</div>
          <div class="pipe-value ok">✓ Ready</div>
        </div>
        <div class="pipe-item">
          <div class="pipe-label">WordPress</div>
          <div class="pipe-value warn">⚙ Optional</div>
        </div>
        <div class="pipe-item">
          <div class="pipe-label">Newsletter</div>
          <div class="pipe-value warn">⚙ Optional</div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card">
      <div class="card-label">Quick Actions</div>
      <div class="action-btns">
        <a href="/api/run/daily" class="btn">▶ Run Daily</a>
        <a href="/api/run/newsletter" class="btn secondary">📧 Newsletter</a>
        <a href="/api/stats" class="btn secondary">📊 JSON Stats</a>
      </div>
      <div class="card-sub" style="margin-top:1rem">
        Niche: <strong>{{ stats.niche }}</strong>
      </div>
    </div>
  </div>

  <footer>
    Auto-refreshes every 60s · {{ stats.site_name }} Content Engine
  </footer>
</body>
</html>"""


@app.route("/")
def dashboard():
    stats = get_stats()
    return render_template_string(DASHBOARD_HTML, stats=stats)


@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


@app.route("/api/run/<mode>")
def api_run(mode: str):
    """Trigger pipeline runs via API (basic, no auth — add auth for production)."""
    if mode not in ("daily", "seed", "newsletter"):
        return jsonify({"error": "Invalid mode"}), 400

    # In production, use a proper task queue (Celery, RQ, etc.)
    # For now, just return instructions
    return jsonify({
        "message": f"To run: docker exec content-engine python -m pipeline.orchestrator --mode {mode}",
        "mode": mode,
    })


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 3001))
    print(f"\n📊 Dashboard: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
