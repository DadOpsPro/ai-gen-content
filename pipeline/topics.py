"""
pipeline/topics.py
──────────────────
Score and filter scraped topics toward Chris's regular work-beat so
drafts are things he can add firsthand commentary on.

Prefer:
  - Java / legacy Java 8 modernization (security + testing)
  - GitLab SAST → Jira custom automation
  - Developer-as-security-champion dual role
  - Claude Security / Mythos-class scans
  - Plain-English CVE explainers for stacks he touches
  - Package registry / CI-CD supply chain when tied to that stack

Deprioritize generic AI industry roundups and vendor news dumps.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

# Phrases that mark a topic as on-beat for Chris.
STACK_KEYWORDS: Sequence[str] = (
    "java 8", "java8", "legacy java", "java modernization",
    "java", "junit", "maven", "gradle", "spring boot", "jdk",
    "gitlab sast", "gitlab ci", "gitlab", "sast", "dast",
    "jira", "security champion", "appsec champion",
    "developer security", "devsecops", "secure sdlc",
    "claude security", "mythos", "claude mythos",
    "cve", "nvd", "owasp", "cwe",
    "package registry", "maven central", "npm registry",
    "supply chain", "ci/cd", "cicd", "ci cd",
    "static analysis", "dependency scanning", "sbom",
    "application security", "appsec",
)

# Generic AI / vendor-news noise Chris cannot speak to firsthand.
DEPRIORITIZE_KEYWORDS: Sequence[str] = (
    "funding", "raises $", "series a", "series b",
    "acquisition", "acquires", "tokenomics",
    "openai announces", "chatgpt app", "gemini launch",
    "this week in ai", "ai industry", "ai news roundup",
    "sovereign ai", "agent wars", "joy metric", "joy wars",
    "enterprise ai conversation", "vendor news",
    "press release", "launches gpt",
)

# RSS / Serper items need at least one of these to stay in the pool
# unless they already match STACK_KEYWORDS.
SECURITY_TESTING_KEYWORDS: Sequence[str] = (
    "security", "sast", "dast", "cve", "vulnerab", "appsec",
    "test", "junit", "owasp", "gitlab", "java", "jira",
    "supply chain", "registry", "champion", "mythos",
    "devsecops", "ci/cd", "cicd",
)


def _haystack(*parts: str) -> str:
    return " ".join(p or "" for p in parts).lower()


def topic_relevance_score(title: str, summary: str = "") -> int:
    """
    Integer score used to rank / drop topics.

    Positive = on Chris's stack. Strongly negative = generic AI dump.
    """
    text = _haystack(title, summary)
    score = 0
    for keyword in STACK_KEYWORDS:
        if keyword in text:
            score += 3
    for keyword in DEPRIORITIZE_KEYWORDS:
        if keyword in text:
            score -= 4
    return score


def is_stack_relevant(title: str, summary: str = "") -> bool:
    """Keep RSS items that touch security/testing or Chris's stack."""
    text = _haystack(title, summary)
    if any(keyword in text for keyword in STACK_KEYWORDS):
        return True
    if any(keyword in text for keyword in DEPRIORITIZE_KEYWORDS):
        return False
    return any(keyword in text for keyword in SECURITY_TESTING_KEYWORDS)


def rank_topics(topics: Iterable, max_topics: int = 30) -> List:
    """
    Sort topics by stack relevance, then search-volume signal.

    Drops strongly off-beat items when enough on-beat ones exist.
    """
    scored = []
    for topic in topics:
        title = getattr(topic, "title", "") or ""
        summary = getattr(topic, "summary", "") or ""
        score = topic_relevance_score(title, summary)
        volume = getattr(topic, "search_volume_signal", 0) or 0
        scored.append((score, volume, topic))

    on_beat = [item for item in scored if item[0] >= 0]
    pool = on_beat if len(on_beat) >= 3 else scored
    pool.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [topic for _, _, topic in pool[:max_topics]]
