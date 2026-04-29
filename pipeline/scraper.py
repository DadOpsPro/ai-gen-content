"""
pipeline/scraper.py
──────────────────
Scrapes trending topics for your niche using:
  1. Serper.dev (Google Search JSON API) — primary
  2. RSS feeds from top niche publications — secondary
  3. Hacker News / Reddit search — signals
"""

import httpx
import feedparser
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import SERPER_API_KEY, TOPIC_CLUSTERS, NICHE


@dataclass
class TrendingTopic:
    title: str
    summary: str
    source_url: str
    source_name: str
    published_date: Optional[str]
    search_volume_signal: int  # 1-10 estimated interest
    keywords: List[str]


# ── RSS FEEDS for AI/Testing niche (customize for your niche) ──────────────────
RSS_FEEDS = [
    ("The New Stack",        "https://thenewstack.io/feed/"),
    ("InfoQ",                "https://www.infoq.com/feed/"),
    ("Dev.to AI tag",        "https://dev.to/feed/tag/ai"),
    ("Hacker News",          "https://hnrss.org/newest?q=AI+testing&points=50"),
    ("Google AI Blog",       "https://blog.research.google/feeds/posts/default"),
    ("Towards Data Science", "https://towardsdatascience.com/feed"),
]


def scrape_serper(query: str, num: int = 10) -> List[Dict]:
    """Search Google via Serper.dev API."""
    if not SERPER_API_KEY:
        print(f"  [WARN] No Serper API key — skipping Google search for '{query}'")
        return []
    try:
        response = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num, "tbs": "qdr:w"},  # past week
            timeout=10,
        )
        data = response.json()
        results = []
        for item in data.get("organic", []):
            results.append({
                "title":   item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url":     item.get("link", ""),
                "source":  item.get("displayLink", ""),
            })
        return results
    except Exception as e:
        print(f"  [ERROR] Serper search failed: {e}")
        return []


def scrape_rss_feeds() -> List[TrendingTopic]:
    """Pull recent items from configured RSS feeds."""
    topics = []
    cutoff = datetime.now() - timedelta(days=14)

    for feed_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                # Filter by date if available
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6])
                    if pub_dt < cutoff:
                        continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")[:400]

                # Only keep relevant items
                relevance_keywords = ["AI", "test", "automat", "LLM", "machine learning",
                                      "quality", "QA", "DevOps", "CI/CD"]
                if not any(k.lower() in (title + summary).lower() for k in relevance_keywords):
                    continue

                topics.append(TrendingTopic(
                    title=title,
                    summary=summary,
                    source_url=entry.get("link", ""),
                    source_name=feed_name,
                    published_date=entry.get("published", ""),
                    search_volume_signal=5,
                    keywords=extract_keywords(title + " " + summary),
                ))
        except Exception as e:
            print(f"  [WARN] RSS feed '{feed_name}' failed: {e}")

    return topics


def scrape_google_trends(topics: List[str]) -> List[TrendingTopic]:
    """Use Serper to find trending articles for each topic cluster."""
    results = []
    for topic in topics:
        query = f"{topic} 2025 site:*.io OR site:*.com -reddit"
        items = scrape_serper(query, num=5)
        for item in items:
            results.append(TrendingTopic(
                title=item["title"],
                summary=item["snippet"],
                source_url=item["url"],
                source_name=item["source"],
                published_date=None,
                search_volume_signal=7,
                keywords=extract_keywords(item["title"] + " " + item["snippet"]),
            ))
    return results


def extract_keywords(text: str) -> List[str]:
    """Simple keyword extractor — replace with spacy/keybert for production."""
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
                 "for", "of", "with", "by", "from", "is", "are", "was", "be"}
    words = [w.strip(".,!?()[]\"'").lower() for w in text.split()]
    keywords = [w for w in words if len(w) > 4 and w not in stopwords]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique[:10]


def deduplicate_topics(topics: List[TrendingTopic]) -> List[TrendingTopic]:
    """Remove near-duplicate topics by title similarity."""
    seen_titles = set()
    unique = []
    for t in topics:
        title_key = t.title.lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique.append(t)
    return unique


def gather_trending_topics(max_topics: int = 30) -> List[TrendingTopic]:
    """
    Main entry point. Gathers trends from all sources and returns
    a deduplicated, ranked list of topics to write about.
    """
    print(f"\n🔍 Gathering trending topics for niche: {NICHE}")
    all_topics: List[TrendingTopic] = []

    # 1. RSS feeds
    print("  → Scanning RSS feeds...")
    rss_topics = scrape_rss_feeds()
    all_topics.extend(rss_topics)
    print(f"     Found {len(rss_topics)} RSS topics")

    # 2. Google search via Serper
    print("  → Querying Google Search (Serper)...")
    google_topics = scrape_google_trends(TOPIC_CLUSTERS[:5])  # limit API calls
    all_topics.extend(google_topics)
    print(f"     Found {len(google_topics)} Google topics")

    # 3. Deduplicate and rank
    unique_topics = deduplicate_topics(all_topics)
    ranked = sorted(unique_topics, key=lambda t: t.search_volume_signal, reverse=True)

    print(f"\n✅ Total unique topics found: {len(ranked)}")
    return ranked[:max_topics]


if __name__ == "__main__":
    topics = gather_trending_topics()
    for i, t in enumerate(topics[:5], 1):
        print(f"\n{i}. {t.title}")
        print(f"   Source: {t.source_name}")
        print(f"   Keywords: {', '.join(t.keywords[:5])}")
