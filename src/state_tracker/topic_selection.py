"""
Topic selection for 50-State Topic Tracker.

Identifies the most trending K-12 topic across states using:
- Keyword matching against priority topics
- State coverage analysis
- Score calculation: unique_state_count × article_count
"""

import re
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.state_tracker.config import (
    PRIORITY_TOPICS,
    DOMAIN_STATE_MAP,
    STATE_DOE_PATTERNS,
    MIN_STATES_FOR_SYNTHESIS,
    MIN_ARTICLES_FOR_SYNTHESIS,
)

# Import US_STATES from categorizer
from src.categorizer import US_STATES

# Title case version for matching
US_STATES_TITLECASE = {s.title() for s in US_STATES}


def extract_states_from_text(text: str) -> set[str]:
    """
    Extract US state names from text.

    Args:
        text: Text to search

    Returns:
        Set of state names (title case)
    """
    if not text:
        return set()

    text_lower = text.lower()
    found_states = set()

    for state in US_STATES:
        # Use word boundary matching to avoid false positives
        if re.search(rf'\b{re.escape(state)}\b', text_lower):
            found_states.add(state.title())

    return found_states


def extract_state_from_domain(url: str) -> str:
    """
    Extract state from domain using mapping.

    Args:
        url: Article URL

    Returns:
        State name or empty string
    """
    if not url:
        return ""

    from urllib.parse import urlparse
    try:
        domain = urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return ""

    # Check direct domain mapping
    if domain in DOMAIN_STATE_MAP:
        return DOMAIN_STATE_MAP[domain]

    # Check state DOE patterns
    for pattern, state in STATE_DOE_PATTERNS.items():
        if pattern in domain:
            return state

    # Check for .gov domains with state names
    if ".gov" in domain:
        for state in US_STATES:
            state_abbrev = state[:2].lower()  # Rough abbreviation
            if state_abbrev in domain or state.replace(" ", "") in domain.lower():
                return state.title()

    return ""


def extract_states_from_article(article: dict) -> set[str]:
    """
    Extract all states mentioned in an article.

    Uses multiple methods:
    1. Title text matching
    2. Summary text matching
    3. Domain mapping
    4. Local reason field (if present)

    Args:
        article: Article dict

    Returns:
        Set of state names
    """
    states = set()

    # From title
    title_states = extract_states_from_text(article.get("title", ""))
    states.update(title_states)

    # From summary
    summary_states = extract_states_from_text(article.get("summary", ""))
    states.update(summary_states)

    # From domain
    url = article.get("resolved_url", article.get("url", ""))
    domain_state = extract_state_from_domain(url)
    if domain_state:
        states.add(domain_state)

    # From local_reason field (may contain state info)
    local_reason = article.get("local_reason", "")
    if local_reason:
        reason_states = extract_states_from_text(local_reason)
        states.update(reason_states)

    # From full_content (if scraped) - limit to first 3000 chars for efficiency
    full_content = article.get("full_content", "")
    if full_content:
        content_states = extract_states_from_text(full_content[:3000])
        states.update(content_states)

    return states


def extract_states_from_articles(articles: list[dict]) -> set[str]:
    """
    Extract all unique states from a list of articles.

    Args:
        articles: List of article dicts

    Returns:
        Set of unique state names
    """
    all_states = set()
    for article in articles:
        article_states = extract_states_from_article(article)
        # Store states on article for later use
        article["states_mentioned"] = list(article_states)
        all_states.update(article_states)
    return all_states


def match_article_to_topics(article: dict) -> dict[str, int]:
    """
    Match an article to priority topics based on keywords.

    Args:
        article: Article dict with title, summary

    Returns:
        Dict of topic_id -> keyword match count
    """
    text = " ".join([
        article.get("title", ""),
        article.get("summary", ""),
    ]).lower()

    topic_matches = {}

    for topic_id, topic_config in PRIORITY_TOPICS.items():
        keywords = topic_config.get("keywords", [])
        match_count = 0

        for keyword in keywords:
            if keyword.lower() in text:
                match_count += 1

        if match_count > 0:
            topic_matches[topic_id] = match_count

    return topic_matches


def score_all_topics(articles: list[dict]) -> dict[str, dict]:
    """
    Score all topics by article count and state coverage.

    Score formula: unique_state_count × article_count

    Args:
        articles: List of local article dicts

    Returns:
        Dict of topic_id -> {score, article_count, states, articles}
    """
    topic_data = defaultdict(lambda: {
        "articles": [],
        "states": set(),
        "total_keyword_matches": 0
    })

    for article in articles:
        # Extract states first
        article_states = extract_states_from_article(article)
        article["states_mentioned"] = list(article_states)

        # Match to topics
        matches = match_article_to_topics(article)

        if not matches:
            # No topic match - could be emergent topic
            continue

        # Assign to best matching topic
        best_topic = max(matches.items(), key=lambda x: x[1])
        topic_id = best_topic[0]
        match_count = best_topic[1]

        topic_data[topic_id]["articles"].append(article)
        topic_data[topic_id]["states"].update(article_states)
        topic_data[topic_id]["total_keyword_matches"] += match_count

    # Calculate scores
    scores = {}
    for topic_id, data in topic_data.items():
        state_count = len(data["states"])
        article_count = len(data["articles"])

        # Score formula: state_count × article_count
        score = state_count * article_count

        scores[topic_id] = {
            "score": score,
            "article_count": article_count,
            "state_count": state_count,
            "states": list(data["states"]),
            "articles": data["articles"],
            "label": PRIORITY_TOPICS.get(topic_id, {}).get("label", topic_id)
        }

    return scores


def select_trending_topic(
    articles: list[dict],
    topic_scores: dict[str, dict]
) -> tuple[str, str, list[dict]]:
    """
    Select the most trending topic.

    Args:
        articles: All local articles
        topic_scores: Scores from score_all_topics()

    Returns:
        Tuple of (topic_id, topic_label, topic_articles)
        Returns (None, None, []) if no topic meets minimums
    """
    if not topic_scores:
        return None, None, []

    # Sort by score descending
    sorted_topics = sorted(
        topic_scores.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    # Find first topic that meets minimums
    for topic_id, data in sorted_topics:
        if (data["state_count"] >= MIN_STATES_FOR_SYNTHESIS and
            data["article_count"] >= MIN_ARTICLES_FOR_SYNTHESIS):
            return topic_id, data["label"], data["articles"]

    # If no topic meets minimums, return the best one anyway
    # (let the main orchestrator decide to skip)
    if sorted_topics:
        top_topic = sorted_topics[0]
        return top_topic[0], top_topic[1]["label"], top_topic[1]["articles"]

    return None, None, []


def get_topic_summary(topic_scores: dict[str, dict]) -> str:
    """
    Get a summary of topic scores for logging.

    Args:
        topic_scores: Scores from score_all_topics()

    Returns:
        Formatted summary string
    """
    if not topic_scores:
        return "No topics matched"

    lines = []
    sorted_topics = sorted(
        topic_scores.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    for topic_id, data in sorted_topics:
        lines.append(
            f"  {data['label']}: score={data['score']} "
            f"({data['state_count']} states × {data['article_count']} articles)"
        )

    return "\n".join(lines)
