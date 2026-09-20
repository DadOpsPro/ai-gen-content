import unittest
from datetime import datetime, timezone

from pipeline.listings import (
    archive_by_month,
    featured_and_recent,
    is_in_listing_window,
    listed_articles,
    load_soft_retired_slugs,
    normalize_slug,
    parse_published_at,
)


NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def rec(slug, published_at, title=None):
    return {
        "slug": slug,
        "title": title or slug,
        "excerpt": f"Pitch for {slug}",
        "category": "AppSec",
        "word_count": 400,
        "published_at": published_at,
    }


class ListingTests(unittest.TestCase):
    def test_parse_zulu_timestamp(self):
        dt = parse_published_at("2026-09-04T12:00:00.000Z")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_soft_retire_hides_old_posts(self):
        fresh = rec("new", "2026-08-01T00:00:00Z")
        old = rec("old", "2025-01-01T00:00:00Z")
        self.assertTrue(is_in_listing_window(fresh, now=NOW))
        self.assertFalse(is_in_listing_window(old, now=NOW))

    def test_missing_date_stays_listed(self):
        undated = rec("undated", None)
        self.assertTrue(is_in_listing_window(undated, now=NOW))

    def test_featured_and_recent_does_not_dump_all(self):
        registry = [
            rec("a", "2026-09-04T00:00:00Z", "Newest"),
            rec("b", "2026-09-03T00:00:00Z", "Two"),
            rec("c", "2026-09-02T00:00:00Z", "Three"),
            rec("d", "2026-09-01T00:00:00Z", "Four"),
            rec("retired", "2024-01-01T00:00:00Z", "Retired"),
        ]
        featured, recent = featured_and_recent(registry, now=NOW, recent_count=3)
        self.assertEqual(featured["slug"], "a")
        self.assertEqual([r["slug"] for r in recent], ["b", "c", "d"])
        self.assertNotIn("retired", [featured["slug"]] + [r["slug"] for r in recent])

    def test_archive_groups_by_month_and_excludes_retired(self):
        registry = [
            rec("sep", "2026-09-04T00:00:00Z"),
            rec("aug", "2026-08-16T00:00:00Z"),
            rec("old", "2025-01-01T00:00:00Z"),
        ]
        groups = archive_by_month(registry, now=NOW)
        labels = [label for label, _ in groups]
        self.assertEqual(labels, ["September 2026", "August 2026"])
        slugs = [article["slug"] for _, articles in groups for article in articles]
        self.assertNotIn("old", slugs)

    def test_listed_articles_reverse_chron(self):
        registry = [
            rec("older", "2026-06-07T00:00:00Z"),
            rec("newer", "2026-09-04T00:00:00Z"),
        ]
        listed = listed_articles(registry, now=NOW)
        self.assertEqual([r["slug"] for r in listed], ["newer", "older"])

    def test_normalize_slug_strips_posts_prefix_and_html(self):
        self.assertEqual(
            normalize_slug("posts/hijack-claude-cursor-codex-via-sentry-keys.html"),
            "hijack-claude-cursor-codex-via-sentry-keys",
        )

    def test_denylist_excludes_from_home_and_archive_not_by_date(self):
        keep = rec("developer-security-champion-dual-role", "2026-09-04T00:00:00Z")
        trend = rec("spacex-cursor-acquisition-ai-coding", "2026-09-03T00:00:00Z")
        broken = rec("hijack-claude-cursor-codex-via-sentry-keys", "2026-09-02T00:00:00Z")
        retired = {"spacex-cursor-acquisition-ai-coding", "hijack-claude-cursor-codex-via-sentry-keys"}
        listed = listed_articles(
            [keep, trend, broken], now=NOW, retired_slugs=retired
        )
        self.assertEqual([r["slug"] for r in listed], [keep["slug"]])
        featured, recent = featured_and_recent(
            [keep, trend, broken], now=NOW, retired_slugs=retired
        )
        self.assertEqual(featured["slug"], keep["slug"])
        self.assertEqual(recent, [])
        groups = archive_by_month(
            [keep, trend, broken], now=NOW, retired_slugs=retired
        )
        slugs = [article["slug"] for _, articles in groups for article in articles]
        self.assertEqual(slugs, [keep["slug"]])

    def test_soft_retire_file_keeps_practitioner_posts(self):
        retired = load_soft_retired_slugs()
        keep = {
            "chainguard-open-source-packages-supply-chain-security",
            "claude-mythos-fable-5-testing-guide",
            "claude-security-mythos-5-enterprise-beta",
            "developer-security-champion-dual-role",
            "gitlab-sast-jira-automate-tickets",
            "package-registry-shai-hulud-ci-cd-security",
        }
        must_retire = {
            "ai-agents-break-free-solo-dev-mode",
            "ai-code-review-better-than-teammates",
            "ai-coding-agents-stack-overflow-integration",
            "ai-generated-apps-cloud-dependency-risks",
            "ai-retrieval-ranking-beyond-vector-search",
            "ai-solving-memory-crunch-trend-roundup",
            "ai-testing-security-weekly-fable-mythos-suspended",
            "anthropic-fable-mess-explained",
            "aws-bill-spike-cost-agent-guide",
            "aws-context-ai-agent-reasoning-trend",
            "checkmarx-sast-engine-post-scan-intelligence",
            "cohere-coding-model-enterprise-developers",
            "cohere-developer-pivot-sovereign-ai-enterprise",
            "cross-repo-review-ai-teams-qodo",
            "cross-repo-review-qodo-ai-teams",
            "downloadable-ai-models-grok-cost-effective-testing",
            "enterprise-agent-wars-neutral-platform",
            "entry-level-tech-jobs-ai-disruption-guide",
            "gemini-cli-vs-antigravity-real-world-performance",
            "google-double-blind-gemini-testing",
            "hijack-claude-cursor-codex-via-sentry-keys",
            "joy-wars-ai-agents-competition-shift",
            "kiro-mobile-aws-agentic-coding-iphone",
            "mcp-enterprise-authorization-layer-implementation",
            "microsoft-azure-repos-github-migration-guide",
            "netlify-cto-dana-lawson-writing-code-no-longer-job",
            "observability-overload-drowning-engineers",
            "optimize-fable-5-guardrails-burn-rate",
            "per-developer-environments-ai-agents-trend",
            "proactive-ai-agents-autonomous-business-operations",
            "protect-ai-coding-agents-sentry-key-exploitation",
            "replace-java-8-spring-boot-angular-strangler",
            "replit-auto-mode-picks-best-model",
            "sentry-key-hijack-claude-cursor-codex-defense",
            "spacex-cursor-acquisition-ai-coding",
            "valkey-ai-automated-backporting-bug-fixes",
        }
        self.assertFalse(keep & retired)
        self.assertTrue(must_retire <= retired)
        self.assertNotIn("claude-mythos-fable-5-testing-guide", retired)

    def test_real_denylist_keeps_only_approved_archive_slugs(self):
        registry = [
            rec("developer-security-champion-dual-role", "2026-09-04T00:00:00Z"),
            rec("claude-mythos-fable-5-testing-guide", "2026-06-15T00:00:00Z"),
            rec("downloadable-ai-models-grok-cost-effective-testing", "2026-08-10T00:00:00Z"),
            rec("microsoft-azure-repos-github-migration-guide", "2026-06-01T00:00:00Z"),
            rec("protect-ai-coding-agents-sentry-key-exploitation", "2026-06-20T00:00:00Z"),
        ]
        listed = listed_articles(registry, now=NOW)
        self.assertEqual(
            [r["slug"] for r in listed],
            [
                "developer-security-champion-dual-role",
                "claude-mythos-fable-5-testing-guide",
            ],
        )


if __name__ == "__main__":
    unittest.main()
