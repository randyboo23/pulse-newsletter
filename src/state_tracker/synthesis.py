"""
Synthesis article generation for 50-State Topic Tracker.

Generates a structured ~600 word article with:
- What's happening (2-3 sentences)
- What's driving it (context)
- What states are doing (themes + 6-10 state snapshots)
- What districts can do this week (3-5 actions)
- What to watch next
- Sources

Includes guardrail flags: [REPORTED] for unverified claims, [VERIFY:] for uncertain inferences.
"""

import os
import json

import anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

from .config import TARGET_WORD_COUNT


def get_anthropic_client() -> anthropic.Anthropic:
    """Initialize Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")
    return anthropic.Anthropic(api_key=api_key)


SYNTHESIS_SYSTEM_PROMPT = """You are writing a 50-State Topic Tracker synthesis for PulseK12, a weekly newsletter for K-12 education leaders.

Voice guidelines:
- Write like a smart insider briefing a colleague
- Assume the reader knows the education space
- Lead sentences with actors/subjects: "District leaders...", "State lawmakers..."
- Use specific numbers when available (ONLY if cited in source text)
- No filler phrases. Direct and declarative.
- End sections with implication, not instruction
- No exclamation points. Professional warmth, not enthusiasm.

CRITICAL GUARDRAILS:
- Every number/statistic must come from a source article. If unsure, omit it.
- Mark claims without primary source verification with [REPORTED] prefix
- Flag uncertain state inferences with [VERIFY: brief reason]
- Do not invent policy details not explicitly stated in sources
- When paraphrasing, stay true to the source meaning

TARGET LENGTH: ~600 words total across all sections."""


SYNTHESIS_USER_PROMPT = """Generate a 50-State Topic Tracker synthesis on: {topic}

SOURCE ARTICLES ({article_count} articles across {state_count} states):
{articles_summary}

IDENTIFIED THEMES:
{themes_text}

STATE COVERAGE: {states_list}

Generate a synthesis with these sections. Respond in JSON format:

{{
  "topic_title": "Compelling title for this week's tracker (include topic name)",
  "whats_happening": "2-3 sentences describing current state across the nation. Plain language.",
  "whats_driving": "2-3 sentences on context: data trends, federal pressure, post-pandemic patterns, preceding events.",
  "state_themes": "3-5 bulleted themes (markdown list). Each theme one sentence.",
  "state_snapshots": "6-10 state snapshots. Format: **State Name**: [specific policy/action] ([source attribution])",
  "district_actions": "3-5 practical moves districts can make this week (markdown list). Concrete and actionable.",
  "watch_next": "2-3 upcoming deadlines, votes, guidance cycles, or developments to monitor (markdown list)."
}}

Remember:
- Mark unverified policy claims with [REPORTED] prefix
- Flag uncertain state inferences with [VERIFY: reason]
- Only include numbers that appear in source articles
- Keep total length ~600 words"""


def build_articles_summary(articles: list[dict]) -> str:
    """Build article summary text for synthesis prompt."""
    summary = ""
    for i, article in enumerate(articles, 1):
        title = article.get("title", "")
        source = article.get("source", "")
        states = article.get("states_mentioned", [])
        tier = article.get("source_tier", "B")

        meta = article.get("metadata", {})
        policy_type = meta.get("policy_type", "")
        data_points = meta.get("key_data_points", [])

        tier_label = {"A": "[Primary]", "B": "", "unknown": ""}.get(tier, "")

        summary += f"""
{i}. {tier_label} "{title}"
   Source: {source} | States: {', '.join(states)}
   Policy: {policy_type}
   Data: {'; '.join(data_points[:2]) if data_points else 'None cited'}
"""
    return summary


def build_themes_text(themes: list[dict]) -> str:
    """Build themes text for synthesis prompt."""
    if not themes:
        return "No specific themes identified"

    lines = []
    for t in themes:
        theme = t.get("theme", "")
        states = t.get("states", [])
        if theme:
            lines.append(f"- {theme} ({', '.join(states[:3])})")
    return "\n".join(lines)


def generate_synthesis_article(
    topic_label: str,
    articles: list[dict],
    themes: list[dict],
    states_covered: set[str]
) -> dict:
    """
    Generate the structured synthesis article.

    Args:
        topic_label: The topic being tracked
        articles: Articles with metadata
        themes: National themes
        states_covered: Set of states covered

    Returns:
        Dict with all article sections
    """
    if not articles:
        return {}

    client = get_anthropic_client()

    articles_summary = build_articles_summary(articles)
    themes_text = build_themes_text(themes)

    prompt = SYNTHESIS_USER_PROMPT.format(
        topic=topic_label,
        article_count=len(articles),
        state_count=len(states_covered),
        articles_summary=articles_summary,
        themes_text=themes_text,
        states_list=", ".join(sorted(states_covered))
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            system=SYNTHESIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        # Parse JSON response
        json_match = response_text
        if "```json" in response_text:
            json_match = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_match = response_text.split("```")[1].split("```")[0]

        synthesis = json.loads(json_match.strip())

        # Ensure all expected keys exist
        expected_keys = [
            "topic_title", "whats_happening", "whats_driving",
            "state_themes", "state_snapshots", "district_actions", "watch_next"
        ]
        for key in expected_keys:
            if key not in synthesis:
                synthesis[key] = ""

        return synthesis

    except json.JSONDecodeError as e:
        print(f"  Warning: Could not parse synthesis JSON: {e}")
        return generate_fallback_synthesis(topic_label, articles, themes, states_covered)
    except Exception as e:
        print(f"  Error generating synthesis: {e}")
        return generate_fallback_synthesis(topic_label, articles, themes, states_covered)


def generate_fallback_synthesis(
    topic_label: str,
    articles: list[dict],
    themes: list[dict],
    states_covered: set[str]
) -> dict:
    """
    Generate a basic fallback synthesis when Claude call fails.

    Args:
        topic_label: The topic being tracked
        articles: Articles with metadata
        themes: National themes
        states_covered: Set of states covered

    Returns:
        Dict with basic article sections
    """
    # Build state snapshots from articles
    state_snapshots = []
    seen_states = set()
    for article in articles:
        states = article.get("states_mentioned", [])
        title = article.get("title", "")
        source = article.get("source", "")
        for state in states:
            if state not in seen_states and len(state_snapshots) < 8:
                state_snapshots.append(f"**{state}**: {title[:60]}... ({source})")
                seen_states.add(state)

    # Build themes list
    theme_bullets = []
    for t in themes[:4]:
        theme = t.get("theme", "")
        if theme:
            theme_bullets.append(f"- {theme}")

    return {
        "topic_title": f"{topic_label}: This Week Across States",
        "whats_happening": f"[REPORTED] Activity on {topic_label.lower()} continues across {len(states_covered)} states this week, with new developments in policy and practice.",
        "whats_driving": "Post-pandemic pressures continue to drive state and district attention to this issue, with federal guidance and funding incentives playing a role.",
        "state_themes": "\n".join(theme_bullets) if theme_bullets else "- Multiple approaches emerging across states",
        "state_snapshots": "\n".join(state_snapshots),
        "district_actions": "- Review your current approach to this area\n- Monitor state guidance for updates\n- Connect with peer districts on implementation",
        "watch_next": "- Ongoing state legislative sessions\n- Federal guidance updates\n- Research and evaluation findings"
    }


def parse_synthesis_response(response_text: str) -> dict:
    """
    Parse synthesis response text into sections.

    Handles both JSON and freeform responses.

    Args:
        response_text: Raw response from Claude

    Returns:
        Dict with article sections
    """
    # Try JSON first
    try:
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0]
        else:
            json_text = response_text

        return json.loads(json_text.strip())
    except (json.JSONDecodeError, IndexError):
        pass

    # Fallback: parse freeform sections
    sections = {
        "topic_title": "",
        "whats_happening": "",
        "whats_driving": "",
        "state_themes": "",
        "state_snapshots": "",
        "district_actions": "",
        "watch_next": ""
    }

    # Simple section parsing
    current_section = None
    current_content = []

    for line in response_text.split("\n"):
        line_lower = line.lower().strip()

        if "what's happening" in line_lower or "whats happening" in line_lower:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "whats_happening"
            current_content = []
        elif "what's driving" in line_lower or "whats driving" in line_lower:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "whats_driving"
            current_content = []
        elif "state themes" in line_lower or "key themes" in line_lower:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "state_themes"
            current_content = []
        elif "state snapshots" in line_lower or "states are doing" in line_lower:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "state_snapshots"
            current_content = []
        elif "district" in line_lower and ("action" in line_lower or "can do" in line_lower):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "district_actions"
            current_content = []
        elif "watch next" in line_lower or "to watch" in line_lower:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = "watch_next"
            current_content = []
        elif current_section:
            current_content.append(line)

    # Capture last section
    if current_section and current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections
