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
from pipeline.topics import is_stack_relevant, rank_topics, topic_relevance_score


@dataclass
class TrendingTopic:
    title: str
    summary: str
    source_url: str
    source_name: str
    published_date: Optional[str]
    search_volume_signal: int  # 1-10 estimated interest
    keywords: List[str]


# RSS feeds biased toward Chris's stack (Java / GitLab / AppSec / CVE),
# not generic AI industry blogs.
RSS_FEEDS = [
    ("InfoQ Java",           "https://feed.infoq.com/Java/"),
    ("InfoQ Security",       "https://feed.infoq.com/security/"),
    ("The New Stack",        "https://thenewstack.io/feed/"),
    ("GitLab Blog",          "https://about.gitlab.com/atom.xml"),
    ("Hacker News AppSec",   "https://hnrss.org/newest?q=Java+OR+SAST+OR+CVE+OR+GitLab&points=30"),
    ("OWASP",                "https://owasp.org/feed.xml"),
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

                if not is_stack_relevant(title, summary):
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
    """Use Serper to find recent articles for each stack-focused topic cluster."""
    results = []
    for topic in topics:
        query = f"{topic} 2026 (Java OR GitLab OR SAST OR CVE OR Jira) -reddit"
        items = scrape_serper(query, num=5)
        for item in items:
            title = item["title"]
            snippet = item["snippet"]
            volume = 7 + min(3, max(0, topic_relevance_score(title, snippet) // 3))
            results.append(TrendingTopic(
                title=title,
                summary=snippet,
                source_url=item["url"],
                source_name=item["source"],
                published_date=None,
                search_volume_signal=volume,
                keywords=extract_keywords(title + " " + snippet),
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

    # 3. Deduplicate, then rank toward Chris's stack (not generic AI news)
    unique_topics = deduplicate_topics(all_topics)
    ranked = rank_topics(unique_topics, max_topics=max_topics)

    print(f"\n✅ Total unique topics found: {len(ranked)} (stack-ranked)")
    return ranked


if __name__ == "__main__":
    topics = gather_trending_topics()
    for i, t in enumerate(topics[:5], 1):
        print(f"\n{i}. {t.title}")
        print(f"   Source: {t.source_name}")
        print(f"   Keywords: {', '.join(t.keywords[:5])}")
