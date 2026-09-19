import unittest
from dataclasses import dataclass

from pipeline.topics import (
    is_stack_relevant,
    rank_topics,
    topic_relevance_score,
)


@dataclass
class FakeTopic:
    title: str
    summary: str = ""
    search_volume_signal: int = 5


class TopicScoringTests(unittest.TestCase):
    def test_stack_topics_score_higher_than_vendor_news(self):
        java = topic_relevance_score(
            "GitLab SAST to Jira: automate security tickets",
            "Wire Java findings into Jira for the security champion.",
        )
        noise = topic_relevance_score(
            "The Joy Wars Begin: AI Agent Competition Shifts",
            "Enterprise AI conversation and vendor news dump.",
        )
        self.assertGreater(java, 0)
        self.assertLess(noise, 0)
        self.assertGreater(java, noise)

    def test_rss_keeps_cve_and_drops_generic_ai_roundup(self):
        self.assertTrue(is_stack_relevant("Plain-English CVE-2026-1234 for Maven", ""))
        self.assertFalse(is_stack_relevant("This week in AI industry funding", "OpenAI announces"))

    def test_rank_topics_prefers_on_beat(self):
        topics = [
            FakeTopic("SpaceX Cursor acquisition tokenomics", "vendor news"),
            FakeTopic("Java 8 modernization: SAST and tests", "legacy java"),
            FakeTopic("Claude Security Mythos scans in GitLab CI", "appsec"),
        ]
        ranked = rank_topics(topics, max_topics=2)
        titles = [t.title for t in ranked]
        self.assertIn("Java 8 modernization: SAST and tests", titles)
        self.assertIn("Claude Security Mythos scans in GitLab CI", titles)
        self.assertNotIn("SpaceX Cursor acquisition tokenomics", titles)


if __name__ == "__main__":
    unittest.main()
