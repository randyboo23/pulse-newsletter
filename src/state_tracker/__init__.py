"""
50-State Topic Tracker for PulseK12.

Replaces the LOCAL SPOTLIGHT section with a structured synthesis article
tracking one trending K-12 topic across multiple states.

Pipeline:
1. Topic Selection - Identify most trending topic (state_count x article_count)
2. Source Tiering - Classify articles as Tier A/B/C
3. Deduplication - Title similarity + semantic clustering
4. Theme Extraction - Tag metadata, generate national themes
5. Synthesis - Generate structured article with guardrails
6. Guardrails - Verify citations, flag uncertain claims
"""

from .config import (
    PRIORITY_TOPICS,
    SOURCE_TIERS,
    MIN_STATES_FOR_SYNTHESIS,
    MIN_ARTICLES_FOR_SYNTHESIS,
)
from .topic_selection import select_trending_topic, score_all_topics
from .source_tiering import classify_source_tier, filter_tier_c
from .deduplication import deduplicate_state_articles
from .theme_extraction import extract_themes_and_metadata
from .synthesis import generate_synthesis_article
from .guardrails import verify_and_flag

__all__ = [
    "run_state_tracker",
    "format_state_tracker_section",
    "StateTrackerResult",
]


class StateTrackerResult:
    """Result from the state tracker pipeline."""

    def __init__(
        self,
        topic: str,
        topic_label: str,
        synthesis: dict,
        articles_used: list,
        states_covered: list,
        themes: list,
        sources: list,
        verification: dict,
        skipped_reason: str = None
    ):
        self.topic = topic
        self.topic_label = topic_label
        self.synthesis = synthesis
        self.articles_used = articles_used
        self.states_covered = states_covered
        self.themes = themes
        self.sources = sources
        self.verification = verification
        self.skipped_reason = skipped_reason

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "topic": self.topic,
            "topic_label": self.topic_label,
            "synthesis": self.synthesis,
            "articles_used": len(self.articles_used),
            "states_covered": self.states_covered,
            "themes": self.themes,
            "sources": self.sources,
            "verification": self.verification,
            "skipped_reason": self.skipped_reason
        }


def run_state_tracker(
    local_articles: list[dict],
    topic_override: str = None,
    max_scrapes: int = 30
) -> StateTrackerResult:
    """
    Run the full 50-State Topic Tracker pipeline.

    Args:
        local_articles: List of local article dicts from the main pipeline
        topic_override: Optional topic ID to force (e.g., "attendance_engagement")
        max_scrapes: Maximum Firecrawl scrapes to use

    Returns:
        StateTrackerResult with synthesis and metadata
    """
    if not local_articles:
        return StateTrackerResult(
            topic="none",
            topic_label="None",
            synthesis={},
            articles_used=[],
            states_covered=[],
            themes=[],
            sources=[],
            verification={},
            skipped_reason="No local articles provided"
        )

    print(f"  Starting state tracker with {len(local_articles)} local articles...")

    # Step 1: Topic Selection
    if topic_override:
        topic_id = topic_override
        topic_label = PRIORITY_TOPICS.get(topic_id, {}).get("label", topic_override)
        topic_articles = local_articles  # Use all if overridden
        print(f"  Topic override: {topic_label}")
    else:
        topic_scores = score_all_topics(local_articles)
        topic_id, topic_label, topic_articles = select_trending_topic(
            local_articles, topic_scores
        )
        if not topic_id:
            return StateTrackerResult(
                topic="none",
                topic_label="None",
                synthesis={},
                articles_used=[],
                states_covered=[],
                themes=[],
                sources=[],
                verification={},
                skipped_reason="No trending topic found with sufficient coverage"
            )
        print(f"  Selected topic: {topic_label} ({len(topic_articles)} articles)")

    # Step 2: Source Tiering
    for article in topic_articles:
        tier, confidence, reason = classify_source_tier(article)
        article["source_tier"] = tier
        article["tier_confidence"] = confidence
        article["tier_reason"] = reason

    # Filter out Tier C
    filtered_articles = filter_tier_c(topic_articles)
    print(f"  After tier filtering: {len(filtered_articles)} articles")

    if len(filtered_articles) < MIN_ARTICLES_FOR_SYNTHESIS:
        return StateTrackerResult(
            topic=topic_id,
            topic_label=topic_label,
            synthesis={},
            articles_used=[],
            states_covered=[],
            themes=[],
            sources=[],
            verification={},
            skipped_reason=f"Insufficient articles after filtering ({len(filtered_articles)} < {MIN_ARTICLES_FOR_SYNTHESIS})"
        )

    # Step 3: Deduplication
    deduped_articles = deduplicate_state_articles(filtered_articles)
    print(f"  After deduplication: {len(deduped_articles)} articles")

    # Step 4: Extract states and check coverage
    from .topic_selection import extract_states_from_articles
    states_covered = extract_states_from_articles(deduped_articles)

    if len(states_covered) < MIN_STATES_FOR_SYNTHESIS:
        return StateTrackerResult(
            topic=topic_id,
            topic_label=topic_label,
            synthesis={},
            articles_used=deduped_articles,
            states_covered=states_covered,
            themes=[],
            sources=[],
            verification={},
            skipped_reason=f"Insufficient state coverage ({len(states_covered)} < {MIN_STATES_FOR_SYNTHESIS})"
        )

    print(f"  States covered: {len(states_covered)} ({', '.join(sorted(states_covered)[:5])}...)")

    # Step 5: Theme Extraction
    themes, articles_with_metadata = extract_themes_and_metadata(
        deduped_articles, topic_label
    )
    print(f"  Extracted {len(themes)} themes")

    # Step 6: Synthesis
    synthesis = generate_synthesis_article(
        topic_label,
        articles_with_metadata,
        themes,
        states_covered
    )

    # Step 7: Guardrails
    verification = verify_and_flag(synthesis, articles_with_metadata)

    # Build source list
    sources = build_source_list(articles_with_metadata)

    return StateTrackerResult(
        topic=topic_id,
        topic_label=topic_label,
        synthesis=synthesis,
        articles_used=articles_with_metadata,
        states_covered=list(states_covered),
        themes=themes,
        sources=sources,
        verification=verification
    )


def build_source_list(articles: list[dict]) -> list[dict]:
    """Build prioritized source list (Tier A first)."""
    seen_domains = set()
    sources = []

    # Sort by tier (A first), then by state count
    def sort_key(a):
        tier_order = {"A": 0, "B": 1, "C": 2}
        tier = a.get("source_tier", "C")
        states = a.get("states_mentioned", [])
        return (tier_order.get(tier, 2), -len(states))

    sorted_articles = sorted(articles, key=sort_key)

    for article in sorted_articles:
        url = article.get("resolved_url", article.get("url", ""))
        source = article.get("source", "Unknown")

        # Simple domain extraction
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.replace("www.", "")
        except Exception:
            domain = url

        if domain and domain not in seen_domains:
            sources.append({
                "title": article.get("title", ""),
                "source": source,
                "url": url,
                "tier": article.get("source_tier", "B"),
                "states": article.get("states_mentioned", [])
            })
            seen_domains.add(domain)

    return sources[:15]  # Cap at 15 sources


def format_state_tracker_section(result: StateTrackerResult) -> str:
    """
    Format the state tracker result for the newsletter menu.

    Args:
        result: StateTrackerResult from run_state_tracker

    Returns:
        Formatted markdown string for the 50-STATE TOPIC TRACKER section
    """
    if result.skipped_reason:
        return f"""---

**50-STATE TOPIC TRACKER**

*{result.skipped_reason}*

"""

    synthesis = result.synthesis
    if not synthesis:
        return ""

    output = """---

**50-STATE TOPIC TRACKER**

"""

    # Topic title
    topic_title = synthesis.get("topic_title", result.topic_label)
    output += f"## {topic_title}\n\n"

    # What's Happening
    if synthesis.get("whats_happening"):
        output += f"**What's Happening**\n{synthesis['whats_happening']}\n\n"

    # What's Driving It
    if synthesis.get("whats_driving"):
        output += f"**What's Driving It**\n{synthesis['whats_driving']}\n\n"

    # What States Are Doing
    if synthesis.get("state_themes") or synthesis.get("state_snapshots"):
        output += "**What States Are Doing**\n"
        if synthesis.get("state_themes"):
            themes = synthesis["state_themes"]
            if isinstance(themes, list):
                output += "\n".join(f"- {t}" if not t.startswith("-") else t for t in themes) + "\n\n"
            else:
                output += themes + "\n\n"
        if synthesis.get("state_snapshots"):
            snapshots = synthesis["state_snapshots"]
            if isinstance(snapshots, list):
                output += "\n".join(snapshots) + "\n\n"
            else:
                output += snapshots + "\n\n"

    # What Districts Can Do
    if synthesis.get("district_actions"):
        output += "**What Districts Can Do This Week**\n"
        actions = synthesis["district_actions"]
        if isinstance(actions, list):
            output += "\n".join(a if a.startswith("-") else f"- {a}" for a in actions) + "\n\n"
        else:
            output += actions + "\n\n"

    # What to Watch
    if synthesis.get("watch_next"):
        output += "**What to Watch Next**\n"
        watch = synthesis["watch_next"]
        if isinstance(watch, list):
            output += "\n".join(w if w.startswith("-") else f"- {w}" for w in watch) + "\n\n"
        else:
            output += watch + "\n\n"

    # Sources
    if result.sources:
        output += "**Sources**\n"
        for src in result.sources[:8]:
            tier_badge = {"A": "[Primary]", "B": "", "C": ""}.get(src.get("tier", "B"), "")
            if tier_badge:
                tier_badge += " "
            output += f"- {tier_badge}[{src['source']}]({src['url']})\n"
        output += "\n"

    # Verification flags for editor
    if result.verification.get("flags_for_review"):
        output += "*Editor note: Some claims flagged for verification - see source list.*\n\n"

    return output
