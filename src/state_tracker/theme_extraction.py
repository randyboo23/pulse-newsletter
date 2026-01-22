"""
Theme extraction for 50-State Topic Tracker.

Uses Claude to:
1. Tag articles with structured metadata (policy type, strategy, grade band, equity lens)
2. Generate 3-5 national themes (the "so what")
"""

import os
import json
from collections import defaultdict

import anthropic
from dotenv import load_dotenv

load_dotenv()

from .config import POLICY_TYPES, STRATEGY_TYPES, GRADE_BANDS


def get_anthropic_client() -> anthropic.Anthropic:
    """Initialize Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")
    return anthropic.Anthropic(api_key=api_key)


METADATA_EXTRACTION_PROMPT = """Analyze these K-12 education articles about "{topic}" and extract structured metadata.

ARTICLES:
{articles_text}

For each article, extract:
1. policy_type: One of {policy_types}
2. strategy_types: List from {strategy_types}
3. grade_band: One of {grade_bands}
4. equity_focus: Brief note if article mentions specific populations (low-income, special ed, ELL, rural, etc.)
5. key_data_points: Any specific numbers or statistics mentioned

Respond in JSON format:
{{
  "articles": [
    {{
      "index": 1,
      "policy_type": "...",
      "strategy_types": ["...", "..."],
      "grade_band": "...",
      "equity_focus": "..." or null,
      "key_data_points": ["...", "..."] or []
    }}
  ]
}}

Be precise. Only include what is explicitly stated in the articles."""


THEME_GENERATION_PROMPT = """Based on these K-12 education articles about "{topic}" across multiple US states, identify 3-5 national themes.

ARTICLES WITH METADATA:
{articles_summary}

STATE COVERAGE: {states_list}

Generate themes that capture the "so what" - patterns that matter for district leaders.

Good theme examples:
- "States are shifting from awareness to compliance on attendance"
- "Funding is increasingly tied to attendance plans and reporting"
- "More emphasis on early warning systems and tiered supports"

Respond in JSON format:
{{
  "themes": [
    {{
      "theme": "Theme statement (one sentence)",
      "evidence": "Brief evidence from articles",
      "states_involved": ["State1", "State2"]
    }}
  ]
}}

Focus on actionable patterns, not just descriptions."""


def extract_article_metadata_batch(
    articles: list[dict],
    topic_label: str,
    client: anthropic.Anthropic = None
) -> list[dict]:
    """
    Extract structured metadata from articles using Claude.

    Batches articles for efficiency.

    Args:
        articles: List of article dicts
        topic_label: The topic being tracked
        client: Optional Anthropic client

    Returns:
        Articles with metadata added
    """
    if not articles:
        return []

    if client is None:
        client = get_anthropic_client()

    # Build articles text for prompt
    articles_text = ""
    for i, article in enumerate(articles, 1):
        title = article.get("title", "Untitled")
        source = article.get("source", "Unknown")
        states = article.get("states_mentioned", [])
        summary = article.get("summary", "")[:300]

        articles_text += f"""
{i}. "{title}"
   Source: {source}
   States: {', '.join(states) if states else 'Unknown'}
   Summary: {summary}
"""

    prompt = METADATA_EXTRACTION_PROMPT.format(
        topic=topic_label,
        articles_text=articles_text,
        policy_types=", ".join(POLICY_TYPES),
        strategy_types=", ".join(STRATEGY_TYPES),
        grade_bands=", ".join(GRADE_BANDS)
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        # Parse JSON response
        # Find JSON in response (may have markdown code block)
        json_match = response_text
        if "```json" in response_text:
            json_match = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_match = response_text.split("```")[1].split("```")[0]

        metadata = json.loads(json_match.strip())

        # Apply metadata to articles
        for item in metadata.get("articles", []):
            idx = item.get("index", 0) - 1  # Convert to 0-indexed
            if 0 <= idx < len(articles):
                articles[idx]["metadata"] = {
                    "policy_type": item.get("policy_type", "none"),
                    "strategy_types": item.get("strategy_types", []),
                    "grade_band": item.get("grade_band", "unspecified"),
                    "equity_focus": item.get("equity_focus"),
                    "key_data_points": item.get("key_data_points", [])
                }

    except json.JSONDecodeError as e:
        print(f"  Warning: Could not parse metadata JSON: {e}")
        # Set default metadata
        for article in articles:
            if "metadata" not in article:
                article["metadata"] = {
                    "policy_type": "none",
                    "strategy_types": [],
                    "grade_band": "unspecified",
                    "equity_focus": None,
                    "key_data_points": []
                }
    except Exception as e:
        print(f"  Error extracting metadata: {e}")
        for article in articles:
            if "metadata" not in article:
                article["metadata"] = {
                    "policy_type": "none",
                    "strategy_types": [],
                    "grade_band": "unspecified",
                    "equity_focus": None,
                    "key_data_points": []
                }

    return articles


def generate_national_themes(
    articles: list[dict],
    topic_label: str,
    states_covered: set[str],
    client: anthropic.Anthropic = None
) -> list[dict]:
    """
    Generate 3-5 national themes from article metadata.

    Args:
        articles: Articles with metadata
        topic_label: The topic being tracked
        states_covered: Set of states covered
        client: Optional Anthropic client

    Returns:
        List of theme dicts
    """
    if not articles:
        return []

    if client is None:
        client = get_anthropic_client()

    # Build summary for theme generation
    articles_summary = ""
    for i, article in enumerate(articles, 1):
        title = article.get("title", "")
        states = article.get("states_mentioned", [])
        meta = article.get("metadata", {})

        articles_summary += f"""
{i}. {title}
   States: {', '.join(states)}
   Policy type: {meta.get('policy_type', 'unknown')}
   Strategies: {', '.join(meta.get('strategy_types', []))}
   Data points: {'; '.join(meta.get('key_data_points', [])[:2])}
"""

    prompt = THEME_GENERATION_PROMPT.format(
        topic=topic_label,
        articles_summary=articles_summary,
        states_list=", ".join(sorted(states_covered))
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        # Parse JSON response
        json_match = response_text
        if "```json" in response_text:
            json_match = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_match = response_text.split("```")[1].split("```")[0]

        result = json.loads(json_match.strip())
        themes = result.get("themes", [])

        # Extract just the theme statements
        return [
            {
                "theme": t.get("theme", ""),
                "evidence": t.get("evidence", ""),
                "states": t.get("states_involved", [])
            }
            for t in themes
            if t.get("theme")
        ]

    except json.JSONDecodeError as e:
        print(f"  Warning: Could not parse themes JSON: {e}")
        return generate_fallback_themes(articles, topic_label)
    except Exception as e:
        print(f"  Error generating themes: {e}")
        return generate_fallback_themes(articles, topic_label)


def generate_fallback_themes(articles: list[dict], topic_label: str) -> list[dict]:
    """
    Generate simple fallback themes from article metadata.

    Used when Claude call fails.

    Args:
        articles: Articles with metadata
        topic_label: The topic being tracked

    Returns:
        List of basic theme dicts
    """
    themes = []

    # Aggregate by policy type
    policy_counts = defaultdict(list)
    for article in articles:
        meta = article.get("metadata", {})
        policy_type = meta.get("policy_type", "none")
        if policy_type != "none":
            policy_counts[policy_type].append(article)

    # Generate theme from dominant policy type
    if policy_counts:
        top_policy = max(policy_counts.items(), key=lambda x: len(x[1]))
        policy_name = top_policy[0].replace("_", " ")
        states = set()
        for a in top_policy[1]:
            states.update(a.get("states_mentioned", []))

        themes.append({
            "theme": f"States are focusing on {policy_name} approaches to {topic_label.lower()}",
            "evidence": f"Based on {len(top_policy[1])} articles across {len(states)} states",
            "states": list(states)[:5]
        })

    # Aggregate by strategy type
    strategy_counts = defaultdict(list)
    for article in articles:
        meta = article.get("metadata", {})
        for strategy in meta.get("strategy_types", []):
            strategy_counts[strategy].append(article)

    if strategy_counts:
        top_strategy = max(strategy_counts.items(), key=lambda x: len(x[1]))
        strategy_name = top_strategy[0].replace("_", " ")
        states = set()
        for a in top_strategy[1]:
            states.update(a.get("states_mentioned", []))

        themes.append({
            "theme": f"{strategy_name.title()} emerges as a common intervention strategy",
            "evidence": f"Mentioned in {len(top_strategy[1])} articles",
            "states": list(states)[:5]
        })

    return themes[:5]


def extract_themes_and_metadata(
    articles: list[dict],
    topic_label: str
) -> tuple[list[dict], list[dict]]:
    """
    Full theme extraction pipeline.

    Args:
        articles: List of article dicts
        topic_label: The topic being tracked

    Returns:
        Tuple of (themes, articles_with_metadata)
    """
    client = get_anthropic_client()

    # Step 1: Extract metadata for all articles
    print("  Extracting article metadata...")
    articles_with_metadata = extract_article_metadata_batch(
        articles, topic_label, client
    )

    # Collect states
    states_covered = set()
    for article in articles_with_metadata:
        states_covered.update(article.get("states_mentioned", []))

    # Step 2: Generate national themes
    print("  Generating national themes...")
    themes = generate_national_themes(
        articles_with_metadata,
        topic_label,
        states_covered,
        client
    )

    return themes, articles_with_metadata
