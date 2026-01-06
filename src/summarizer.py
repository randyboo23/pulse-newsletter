"""
Article summarization module using Claude 3.5 Sonnet.
Generates newsletter-style summaries with headline, gist, and why-it-matters.
"""

import os
import sys
from typing import Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.categories import CATEGORIES, format_category_label
from src.scraper import get_content_for_summary


# System prompt encoding voice/tone guidelines (matched to PulseK12 style)
SYSTEM_PROMPT = """You are a newsletter writer for PulseK12, a weekly newsletter for K-12 education leaders.

Voice and style guidelines:
- Write like a smart insider briefing a colleague. Assume the reader knows the education space.
- Lead sentences with the actor/subject: "District leaders...", "Rural students...", "A new study..."
- Use specific numbers when available: "more than 15 percentage points", "over half"
- Never start sentences with "However," "Additionally," "Furthermore," or "Moreover"
- No filler phrases. No hedging. Direct and declarative.
- Weave the significance into the summary naturally — don't preach or lecture about why it matters
- End with implication, not instruction. Let the reader draw conclusions.
- No exclamation points. Professional warmth, not enthusiasm.

You will receive article content and must output a structured summary."""


def get_anthropic_client() -> anthropic.Anthropic:
    """Initialize Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")
    return anthropic.Anthropic(api_key=api_key)


def summarize_article(
    article: dict,
    client: Optional[anthropic.Anthropic] = None
) -> dict:
    """
    Generate a newsletter summary for a single article.

    Args:
        article: Article dict with title, url, content, category
        client: Optional Anthropic client

    Returns:
        Dict with summary components
    """
    if client is None:
        client = get_anthropic_client()

    content = get_content_for_summary(article)
    category_id = article.get("category", "teaching")
    category = CATEGORIES.get(category_id, {})
    category_emoji = category.get("emoji", "📰")

    user_prompt = f"""Summarize this article for the PulseK12 newsletter.

ARTICLE TITLE: {article.get('title', 'Untitled')}
SOURCE: {article.get('source', 'Unknown')}
CATEGORY: {category.get('name', 'General')}

ARTICLE CONTENT:
{content}

---

Provide your summary in this exact format:

HEADLINE: [5-10 word headline. Action-oriented, captures the key news. Examples: "AI Use Is Rising Faster Than School Guidance" or "Rural Students Graduate More, Enroll Less"]

SUMMARY: [Exactly 3 sentences. First sentence sets up the situation. Second adds key details or evidence (use specific numbers if available). Third sentence implies the significance without being preachy. Write as one flowing paragraph.]"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        # Parse the response
        response_text = response.content[0].text
        summary = parse_summary_response(response_text)

        return {
            "success": True,
            "headline": summary.get("headline", article.get("title")),
            "summary": summary.get("summary", ""),
            "category_emoji": category_emoji,
            "category_name": category.get("name", "General"),
            "source_url": article.get("url", ""),
            "source_name": article.get("source", "Unknown"),
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "headline": article.get("title", "Untitled"),
            "summary": "",
            "category_emoji": category_emoji,
            "category_name": category.get("name", "General"),
            "source_url": article.get("url", ""),
            "source_name": article.get("source", "Unknown"),
            "error": str(e)
        }


def parse_summary_response(text: str) -> dict:
    """Parse Claude's response into structured components."""
    result = {
        "headline": "",
        "summary": ""
    }

    lines = text.strip().split("\n")
    current_field = None
    current_content = []

    for line in lines:
        line_upper = line.upper().strip()

        if line_upper.startswith("HEADLINE:"):
            if current_field and current_content:
                result[current_field] = " ".join(current_content).strip()
            current_field = "headline"
            current_content = [line.split(":", 1)[1].strip() if ":" in line else ""]

        elif line_upper.startswith("SUMMARY:"):
            if current_field and current_content:
                result[current_field] = " ".join(current_content).strip()
            current_field = "summary"
            current_content = [line.split(":", 1)[1].strip() if ":" in line else ""]

        elif current_field and line.strip():
            current_content.append(line.strip())

    # Don't forget the last field
    if current_field and current_content:
        result[current_field] = " ".join(current_content).strip()

    return result


def is_complete_summary(summary: dict) -> bool:
    """
    Check if a summary has all required fields populated.

    Returns True if headline and summary are both non-empty with meaningful content.
    """
    if not summary.get("success", False):
        return False

    headline = summary.get("headline", "").strip()
    summary_text = summary.get("summary", "").strip()

    # Both fields must have meaningful content
    return (
        len(headline) > 5 and
        len(summary_text) > 50  # 3 sentences should be at least 50 chars
    )


def count_complete_summaries(summaries: list[dict]) -> tuple[int, int]:
    """Count complete vs incomplete summaries."""
    complete = sum(1 for s in summaries if is_complete_summary(s))
    incomplete = len(summaries) - complete
    return complete, incomplete


def summarize_all_articles(articles: list[dict]) -> list[dict]:
    """
    Generate summaries for all articles.

    Args:
        articles: List of article dicts with content

    Returns:
        List of summary dicts
    """
    client = get_anthropic_client()
    summaries = []

    print(f"Summarizing {len(articles)} articles with Claude...")

    for i, article in enumerate(articles):
        title = article.get("title", "Untitled")[:50]
        print(f"  [{i+1}/{len(articles)}] Summarizing: {title}...")

        summary = summarize_article(article, client)
        summaries.append(summary)

        if not summary["success"]:
            print(f"    Warning: {summary['error']}")

    success_count = sum(1 for s in summaries if s["success"])
    print(f"Summarization complete: {success_count}/{len(summaries)} succeeded")

    return summaries


def format_summary_markdown(summary: dict, include_source: bool = False) -> str:
    """Format a single summary as markdown for the newsletter menu."""
    headline = summary.get("headline", "Untitled")
    url = summary.get("source_url", "#")
    emoji = summary.get("category_emoji", "📰")
    summary_text = summary.get("summary", "")

    # Menu format (for review email)
    result = f"""{emoji} **{headline}**
{summary_text}
"""
    if include_source:
        source = summary.get("source_name", "Unknown")
        result += f"*Source: {source}*\n"

    return result


def format_summary_for_final(summary: dict, number: int, category_name: str) -> str:
    """Format a single summary for the final newsletter issue."""
    headline = summary.get("headline", "Untitled")
    url = summary.get("source_url", "#")
    emoji = summary.get("category_emoji", "📰")
    summary_text = summary.get("summary", "")

    return f"""{number}️⃣ {category_name}
{emoji} [{headline}]({url})
{summary_text}
"""


if __name__ == "__main__":
    # Test summarization (requires ANTHROPIC_API_KEY)
    test_article = {
        "title": "Schools Adopt AI Tutoring Tools",
        "source": "EdWeek",
        "url": "https://example.com/ai-tutoring",
        "category": "ai_edtech",
        "full_content": """
        School districts across the country are increasingly adopting AI-powered
        tutoring tools to help students catch up after pandemic learning losses.
        A new survey from the RAND Corporation found that 45% of districts now
        use some form of AI tutoring software, up from just 12% in 2021.

        The tools, which include platforms like Khanmigo and Carnegie Learning,
        use large language models to provide personalized feedback and explanations
        to students. Early results show promise: students using AI tutors for
        30 minutes daily showed a 15% improvement in math scores compared to
        control groups.

        Critics worry about data privacy and the potential for AI to replace
        human teachers, but proponents argue these tools are meant to supplement,
        not replace, classroom instruction.
        """
    }

    print("Testing summarization...")
    summary = summarize_article(test_article)

    if summary["success"]:
        print("\n" + format_summary_markdown(summary))
    else:
        print(f"Failed: {summary['error']}")
