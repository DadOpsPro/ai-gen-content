# 🤖 AI-Powered Content & Affiliate Engine

An automated pipeline that scrapes trends → generates SEO articles with Claude AI → publishes to a static site or WordPress → sends newsletters → monetizes with ads + affiliates + premium reports.

---

## 🏗️ Architecture

```
Trends (RSS + Google)
        ↓
  Claude AI Generator
        ↓
  ┌─────┴──────┐
  │            │
Static Site  WordPress
  │            │
  └─────┬──────┘
        ↓
  Mailchimp Newsletter
        ↓
  AdSense + Affiliates + Stripe
```

---

## ⚡ Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/yourname/content-engine
cd content-engine
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY at minimum
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Preview your content calendar

```bash
python -m pipeline.orchestrator --mode plan
```

### 4. Generate your seed articles (15 articles)

```bash
python -m pipeline.orchestrator --mode seed
```

Generated HTML will appear in `site/output/posts/`.

### 5. Run daily (pick one)

**Option A — Local cron:**
```bash
# Add to crontab: crontab -e
0 7 * * * cd /path/to/content-engine && python -m pipeline.orchestrator --mode daily
```

**Option B — Docker:**
```bash
cd docker
docker compose up -d
```

**Option C — GitHub Actions (free, zero server):**
Push to GitHub → add secrets → Actions runs daily automatically.

---

## 📁 Project Structure

```
content-engine/
├── config/
│   └── settings.py          # ← Edit your niche, APIs, affiliates here
├── pipeline/
│   ├── scraper.py            # Trend scraping (RSS + Google)
│   ├── generator.py          # Claude AI article generation
│   ├── publisher.py          # Static site + WordPress + Mailchimp
│   ├── orchestrator.py       # Main runner (seed/daily/newsletter)
│   └── premium.py            # Stripe premium reports
├── dashboard/
│   └── app.py                # Flask monitoring dashboard
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
├── site/output/              # Generated static site (gitignored)
├── .github/workflows/        # GitHub Actions auto-publish
├── .env.example
├── requirements.txt
└── state.json                # Tracks published articles (auto-created)
```

---

## 🎯 Customizing Your Niche

Edit `config/settings.py`:

```python
NICHE = "AI in Software Testing"   # ← Your niche
SITE_NAME = "TestAI Weekly"        # ← Your brand

TOPIC_CLUSTERS = [
    "AI test automation tools",
    "LLM testing strategies",
    # ... add your topics
]

AFFILIATE_LINKS = {
    "Playwright": "https://...",   # ← Your affiliate URLs
    "Cypress":    "https://...",
}
```

**Other niche ideas this works for:**
- AI in Application Security (`AppSec AI Weekly`)
- Peptide research & governance (`PeptideInsider`)
- No-code/low-code tools (`NoCodeStack`)
- AI for finance / fintech (`FinAI Digest`)
- Developer productivity tools (`DevToolsWeekly`)

---

## 💰 Monetization Setup

### Google AdSense
1. Apply at [adsense.google.com](https://adsense.google.com)
2. Add your Publisher ID + Slot ID to `.env`
3. Ads auto-inject after the first H2 and at article end

### Amazon Associates
1. Sign up at [affiliate-program.amazon.com](https://affiliate-program.amazon.com)
2. Add your tracking tag to `.env`: `AMAZON_TAG=yourtag-20`
3. Tool names in `AFFILIATE_LINKS` auto-link on first mention

### Other Affiliate Programs
Add any program to `AFFILIATE_LINKS` in `settings.py`:
```python
AFFILIATE_LINKS = {
    "YourTool": "https://yourtool.com?ref=yoursite",
}
```
The generator will naturally insert links when it mentions these tools.

### Premium Reports (Stripe)
```python
from pipeline.premium import create_premium_product

product = create_premium_product(
    title="The Complete Guide to AI Testing in 2025",
    description="40-page deep dive with benchmarks and tool comparisons",
    price_usd=29
)
print(product["payment_link"])  # Share this URL
```

---

## 📧 Newsletter Setup (Mailchimp)

1. Create free Mailchimp account
2. Create an audience (list)
3. Get API key: Account → Extras → API Keys
4. Add `MAILCHIMP_API_KEY` and `MAILCHIMP_LIST_ID` to `.env`
5. Run: `python -m pipeline.orchestrator --mode newsletter`
6. Review campaign in Mailchimp dashboard, then send

---

## 🚀 Deploy Options

### GitHub Pages (Free — recommended to start)
1. Push repo to GitHub
2. Add all secrets in Settings → Secrets → Actions
3. Enable GitHub Pages (source: `gh-pages` branch)
4. GitHub Actions runs the pipeline daily for free

### VPS / DigitalOcean ($6/mo)
```bash
git clone ... && cd content-engine
cp .env.example .env && nano .env
cd docker && docker compose up -d
```

### Netlify / Vercel (Free static hosting)
Point to `site/output` directory after running seed pipeline.

---

## 📊 Dashboard

```bash
python dashboard/app.py
# Visit http://localhost:3001
```

Shows: article count, estimated traffic, revenue projections, pipeline health.

---

## 🔄 Pipeline Modes

| Mode | Command | When to use |
|------|---------|-------------|
| `plan` | `--mode plan` | Preview content calendar |
| `seed` | `--mode seed` | First run — generate 15 articles |
| `daily` | `--mode daily` | Ongoing — 1-2 new articles/day |
| `newsletter` | `--mode newsletter` | Weekly email digest |

---

## 📈 SEO Strategy

The content calendar uses a deliberate mix:

- **How-to guides** (40%) — High search intent, long tail keywords
- **Tool reviews** (25%) — Commercial intent, monetization-ready  
- **Comparisons** (20%) — Buyer intent, "X vs Y" searches
- **Trend roundups** (10%) — Fresh content, newsletter fuel
- **Deep dives** (5%) — Authority building, backlink magnets

Target: 15 seed articles → 3 months → first organic traffic.

---

## ⚠️ Legal Requirements

Add these pages to your site (templates included in `site/output/`):

1. **Affiliate Disclosure** — Required by FTC for US sites
2. **Privacy Policy** — Required for AdSense + GDPR
3. **Terms of Service** — Protects you legally

The affiliate disclaimer is auto-injected at the top of every article.

---

## 🛠️ Extending the System

**Add a new article type:**
```python
# In generator.py, add to ARTICLE_PROMPTS:
ARTICLE_PROMPTS["interview"] = """Write an expert interview..."""
```

**Add a new publish destination:**
```python
# In publisher.py, add a new Publisher class:
class SubstackPublisher:
    def publish(self, article): ...
```

**Add a new scraper source:**
```python
# In scraper.py, add to RSS_FEEDS:
RSS_FEEDS.append(("Your Source", "https://yoursource.com/feed"))
```

---

## 📝 Notes

- Article generation costs ~$0.01–0.03 per article with Claude
- 15 seed articles ≈ $0.30–0.45 in API costs
- Daily mode ≈ $2–5/month in API costs
- AdSense requires 20-30 articles and real traffic before approval
- Mediavine/AdThrive require 50K+ monthly sessions

---

*Built with Claude (Anthropic), Python, and a lot of caffeine.*
