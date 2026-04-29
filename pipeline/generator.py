"""
pipeline/generator.py
─────────────────────
Uses Claude (Anthropic API) to:
  1. Generate full SEO-optimised blog articles
  2. Create newsletter digests
  3. Write premium report sections
  4. Auto-insert affiliate links naturally
"""

import anthropic
import json
import re
import time
import sys
import os
from typing import Optional, List, Dict
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import (
    ANTHROPIC_API_KEY, NICHE, SITE_NAME, AUTHOR_NAME,
    AFFILIATE_LINKS, AMAZON_TAG, MIN_WORD_COUNT, MAX_WORD_COUNT
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


@dataclass
class GeneratedArticle:
    title: str
    slug: str
    meta_description: str
    content_html: str
    excerpt: str
    tags: List[str]
    category: str
    seo_keywords: List[str]
    word_count: int
    article_type: str
    affiliate_links_inserted: List[str]


# ── ARTICLE TYPE PROMPTS ───────────────────────────────────────────────────────

ARTICLE_PROMPTS = {
    "tool_review": """
You are an expert technical writer for {site_name}, a publication focused on {niche}.
Write a comprehensive, honest tool review article.

Topic: {topic}
Additional context: {context}

Structure:
1. Hook opener (problem this tool solves)
2. What is it? (1 paragraph)
3. Key Features (5-7 bullet points with detail)
4. Hands-On Experience (practical perspective)
5. Pricing & Plans
6. Pros and Cons (honest, balanced)
7. Who Should Use It
8. Verdict & Score (/10)
9. FAQ (3-4 questions)

Requirements:
- {min_words}–{max_words} words
- Include specific, concrete details — not vague generalities
- Use H2/H3 headers (##/###)
- Include at least 2 code examples where relevant
- SEO-friendly: naturally use these keywords: {keywords}
- IMPORTANT: Where appropriate, recommend these tools using [[TOOL:ToolName]] placeholders: {tool_names}
- Tone: authoritative but approachable, like a senior dev writing for peers
- End with a strong CTA
""",

    "how_to_guide": """
You are an expert technical writer for {site_name}, focused on {niche}.
Write a practical, step-by-step how-to guide.

Topic: {topic}
Additional context: {context}

Structure:
1. Why This Matters (problem statement)
2. Prerequisites
3. Step-by-Step Instructions (numbered, detailed)
4. Common Pitfalls & How to Avoid Them
5. Real-World Example / Code Walkthrough
6. Summary & Next Steps

Requirements:
- {min_words}–{max_words} words
- Include working code examples with explanations
- Use H2/H3 headers
- Target keyword: {keywords}
- Tool recommendations with [[TOOL:ToolName]] where natural
- Practical, actionable — every step must be concrete
""",

    "trend_roundup": """
You are a sharp tech journalist writing for {site_name} about {niche}.
Write a weekly trend roundup article.

This week's themes: {topic}
Context/signals: {context}

Structure:
1. Editor's Take (2-3 sentences: the big picture)
2. Trend 1: [Name] — what's happening, why it matters, what to do
3. Trend 2: [Name] — same
4. Trend 3: [Name] — same
5. Trend 4: [Name] — same  
6. Tool Spotlight (brief mention of a relevant tool)
7. Stat of the Week
8. What to Watch Next

Requirements:
- {min_words}–{max_words} words
- Fresh, opinionated takes — don't be neutral to the point of being useless
- Include specific numbers/data where you can
- Keywords: {keywords}
- Use [[TOOL:ToolName]] for relevant tool mentions
- Include a forward-looking conclusion
""",

    "comparison": """
You are a technical analyst for {site_name} covering {niche}.
Write a detailed comparison article.

Topic: {topic}
Context: {context}

Structure:
1. Why This Comparison Matters
2. Quick Verdict Table (markdown table)
3. Deep Dive: Option A
4. Deep Dive: Option B  
5. Head-to-Head: 6-8 criteria compared
6. Performance Benchmarks (realistic estimates or cited data)
7. Pricing Comparison
8. When to Choose Each
9. Final Verdict

Requirements:
- {min_words}–{max_words} words
- Include a comparison table
- Be decisive — give a clear winner for different use cases
- Keywords: {keywords}
- Use [[TOOL:ToolName]] for both tools being compared
- Balanced but opinionated
""",

    "deep_dive": """
You are a principal engineer and technical author for {site_name} covering {niche}.
Write a comprehensive deep-dive guide that becomes the definitive resource on this topic.

Topic: {topic}
Context: {context}

Structure:
1. Executive Summary (3-4 sentences)
2. Background & Context
3. Core Concepts (with diagrams described in text)
4. Implementation Deep Dive (detailed, technical)
5. Advanced Techniques
6. Architecture Patterns
7. Performance & Scale Considerations
8. Security Implications
9. Tooling Ecosystem
10. Future Outlook
11. Resources & Further Reading

Requirements:
- {min_words}–{max_words} words  
- This is your flagship content — be thorough
- Multiple code examples
- Keywords: {keywords}
- Use [[TOOL:ToolName]] naturally throughout
- Suitable for senior engineers
""",
}


def generate_article(
    topic: str,
    article_type: str = "how_to_guide",
    context: str = "",
    keywords: List[str] = None,
) -> GeneratedArticle:
    """Generate a full article using Claude."""

    keywords = keywords or []
    tool_names = list(AFFILIATE_LINKS.keys())
    prompt_template = ARTICLE_PROMPTS.get(article_type, ARTICLE_PROMPTS["how_to_guide"])

    prompt = prompt_template.format(
        site_name=SITE_NAME,
        niche=NICHE,
        topic=topic,
        context=context[:500],
        min_words=MIN_WORD_COUNT,
        max_words=MAX_WORD_COUNT,
        keywords=", ".join(keywords[:8]),
        tool_names=", ".join(tool_names),
    )

    print(f"\n✍️  Generating [{article_type}]: {topic[:60]}...")

    # Generate the article content
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_content = response.content[0].text

    # Generate metadata in a second pass
    meta_prompt = f"""Given this article content, provide JSON metadata:

Article title hint: {topic}
Article type: {article_type}

Return ONLY valid JSON (no markdown):
{{
  "title": "SEO-optimised H1 title (60 chars max)",
  "slug": "url-friendly-slug",
  "meta_description": "155-char meta description",
  "excerpt": "2-sentence excerpt for previews",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "category": "main category",
  "seo_keywords": ["kw1", "kw2", "kw3"]
}}

Article beginning:
{raw_content[:800]}"""

    meta_response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": meta_prompt}],
    )

    meta = {}
    try:
        meta_text = meta_response.content[0].text.strip()
        # Strip markdown fences if present
        meta_text = re.sub(r"^```json\s*|\s*```$", "", meta_text, flags=re.MULTILINE)
        meta = json.loads(meta_text)
    except Exception as e:
        print(f"  [WARN] Meta parsing failed: {e}")
        meta = {
            "title": topic[:60],
            "slug": slugify(topic),
            "meta_description": topic[:155],
            "excerpt": topic,
            "tags": keywords[:5],
            "category": NICHE,
            "seo_keywords": keywords[:3],
        }

    # Convert markdown to HTML and inject affiliate links
    html_content, injected_links = convert_and_inject(raw_content)

    word_count = len(raw_content.split())

    return GeneratedArticle(
        title=meta.get("title", topic),
        slug=meta.get("slug", slugify(topic)),
        meta_description=meta.get("meta_description", ""),
        content_html=html_content,
        excerpt=meta.get("excerpt", ""),
        tags=meta.get("tags", []),
        category=meta.get("category", NICHE),
        seo_keywords=meta.get("seo_keywords", keywords),
        word_count=word_count,
        article_type=article_type,
        affiliate_links_inserted=injected_links,
    )


def convert_and_inject(markdown_content: str) -> tuple:
    """
    Convert markdown to HTML and inject affiliate links.
    Returns (html_content, list_of_injected_tool_names)
    """
    # Simple markdown → HTML conversion
    html = markdown_content

    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold / italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Code blocks
    html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code class="language-\1">\2</code></pre>',
                  html, flags=re.DOTALL)
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)

    # Bullet lists
    html = re.sub(r'^\s*[-*] (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>\n?)+', lambda m: f'<ul>\n{m.group()}</ul>\n', html, flags=re.DOTALL)

    # Numbered lists
    html = re.sub(r'^\d+\. (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)

    # Paragraphs
    html = re.sub(r'\n\n(?!<)', '\n</p>\n<p>', html)
    html = f'<p>{html}</p>'

    # Inject affiliate links for [[TOOL:ToolName]] placeholders
    injected = []
    def replace_tool(match):
        tool_name = match.group(1)
        url = AFFILIATE_LINKS.get(tool_name)
        if url:
            injected.append(tool_name)
            return (f'<a href="{url}" target="_blank" rel="noopener nofollow" '
                    f'class="affiliate-link">{tool_name}</a>')
        return tool_name

    html = re.sub(r'\[\[TOOL:([^\]]+)\]\]', replace_tool, html)

    # Also auto-link tool names mentioned naturally (only first occurrence)
    for tool_name, url in AFFILIATE_LINKS.items():
        if tool_name not in injected:
            # Only link the first mention of each tool
            pattern = rf'\b({re.escape(tool_name)})\b'
            replacement = (f'<a href="{url}" target="_blank" rel="noopener nofollow" '
                          f'class="affiliate-link">\\1</a>')
            new_html = re.sub(pattern, replacement, html, count=1)
            if new_html != html:
                injected.append(tool_name)
                html = new_html

    return html, injected


def generate_newsletter(articles: List[GeneratedArticle], week_number: int) -> str:
    """Generate a weekly newsletter digest from recent articles."""
    article_summaries = "\n".join([
        f"- {a.title}: {a.excerpt}"
        for a in articles[:5]
    ])

    prompt = f"""Write a weekly newsletter for {SITE_NAME} readers.
This week's articles:
{article_summaries}

Format:
1. Short, punchy intro (2 sentences — like a message from a friend)
2. 🔥 This Week's Must-Read (feature one article with 3-4 sentence tease)
3. Quick Hits (other articles, 1-2 sentences each)
4. 💡 Tip of the Week (practical, immediately useful)
5. 🛠️ Tool Spotlight (one tool mention, with value prop)
6. Outro + CTA to visit site

Tone: conversational, smart, not corporate. 300-400 words total.
Include plain HTML formatting (no markdown).
Add this affiliate disclaimer at the bottom:
<p class="disclaimer">Some links in this newsletter are affiliate links. We earn a small commission at no cost to you.</p>"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def slugify(text: str) -> str:
    """Convert text to URL slug."""
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:60]


def plan_content_calendar(topics_count: int = 20) -> List[Dict]:
    """Generate a content calendar mixing article types strategically."""
    from config.settings import TOPIC_CLUSTERS, ARTICLE_TYPES

    # SEO strategy: mix of types for maximum coverage
    type_rotation = [
        "how_to_guide",   # High search intent
        "tool_review",    # High commercial intent
        "trend_roundup",  # Fresh, frequent traffic
        "comparison",     # High buyer intent
        "how_to_guide",
        "deep_dive",      # Authoritative, backlink magnet
        "tool_review",
        "how_to_guide",
        "comparison",
        "trend_roundup",
    ]

    calendar = []
    for i in range(topics_count):
        article_type = type_rotation[i % len(type_rotation)]
        topic_base = TOPIC_CLUSTERS[i % len(TOPIC_CLUSTERS)]

        # Generate specific topic angles per type
        angles = {
            "tool_review":    f"Best {topic_base} tools: In-depth review",
            "how_to_guide":   f"How to implement {topic_base} in 2025",
            "trend_roundup":  f"Latest trends in {topic_base}",
            "comparison":     f"{topic_base}: Top tools compared",
            "deep_dive":      f"Complete guide to {topic_base}",
        }
        topic = angles.get(article_type, f"Guide to {topic_base}")

        calendar.append({
            "index":        i + 1,
            "article_type": article_type,
            "topic":        topic,
            "keywords":     [topic_base, NICHE, "2025"],
            "priority":     "high" if i < 5 else "medium",
        })

    return calendar


if __name__ == "__main__":
    # Quick test
    article = generate_article(
        topic="How to use AI to generate test cases automatically",
        article_type="how_to_guide",
        keywords=["AI test generation", "automated testing", "LLM testing"],
    )
    print(f"\n✅ Generated: {article.title}")
    print(f"   Words: {article.word_count}")
    print(f"   Affiliates injected: {article.affiliate_links_inserted}")
    print(f"\nExcerpt: {article.excerpt}")
