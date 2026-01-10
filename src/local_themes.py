"""
Local story theme clustering module.
Uses Claude to group local stories by theme and generate synthesized blurbs.

Example output:
- "School choice momentum: Texas, Florida, and Ohio each advanced voucher legislation..."
- "Budget battles: Districts from California to New York announce hiring freezes..."
"""

import os
import sys
from typing import Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.categorizer import US_STATES

# Valid US state names for filtering (title case for matching)
US_STATES_TITLECASE = {s.title() for s in US_STATES}
# Add common abbreviations and variations
US_STATE_VARIATIONS = US_STATES_TITLECASE | {
    "New York", "North Carolina", "South Carolina", "North Dakota", "South Dakota",
    "New Jersey", "New Mexico", "New Hampshire", "West Virginia", "Rhode Island",
    "DC", "D.C.", "Washington DC", "Washington D.C."
}


THEME_SYSTEM_PROMPT = """You are a newsletter writer for PulseK12, a weekly newsletter for K-12 education leaders.

Your task is to identify themes across local education news stories and synthesize them into compelling blurbs.

IMPORTANT: This is a US-only newsletter. Only include stories about US states and districts.
- Exclude any stories about Canada (Ontario, British Columbia, etc.), UK, Australia, or other countries
- Only reference US states in your themes (e.g., Texas, California, New York)

Voice and style guidelines:
- Write like a smart insider briefing a colleague
- Lead with the theme, then cite specific US states/districts as evidence
- Use specific numbers when available
- No filler phrases. Direct and declarative.
- Each blurb should synthesize 2-4 related stories into one cohesive narrative
- End with implication, not instruction"""


def get_anthropic_client() -> anthropic.Anthropic:
    """Initialize Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")
    return anthropic.Anthropic(api_key=api_key)


def filter_us_states(states: list[str]) -> list[str]:
    """
    Filter a list of locations to only include valid US states.

    Args:
        states: List of location strings

    Returns:
        List containing only valid US state names
    """
    us_only = []
    for state in states:
        state_clean = state.strip()
        # Check against our valid US states set
        if state_clean in US_STATE_VARIATIONS:
            us_only.append(state_clean)
        # Also check lowercase match
        elif state_clean.lower() in US_STATES:
            us_only.append(state_clean.title())
    return us_only


def cluster_local_stories(
    local_articles: list[dict],
    max_themes: int = 2,
    client: Optional[anthropic.Anthropic] = None
) -> list[dict]:
    """
    Cluster local stories by theme and generate synthesized blurbs.

    Args:
        local_articles: List of local article dicts with title, source, summary
        max_themes: Maximum number of themes to generate (1-2 recommended)
        client: Optional Anthropic client

    Returns:
        List of theme dicts with:
        - theme_title: Short theme label (e.g., "School Choice Momentum")
        - blurb: Synthesized 2-3 sentence summary
        - article_indices: List of article indices included in this theme
        - states_mentioned: List of states/locations mentioned
    """
    if not local_articles:
        return []

    if client is None:
        client = get_anthropic_client()

    # Build article list for prompt
    articles_text = ""
    for i, article in enumerate(local_articles):
        title = article.get("title", "Untitled")
        source = article.get("source", "Unknown")
        # Use existing summary if available, otherwise use title
        summary = article.get("summary", "") or article.get("headline", "")
        local_reason = article.get("local_reason", "")

        articles_text += f"""
{i+1}. "{title}"
   Source: {source}
   Location hint: {local_reason}
   Summary: {summary if summary else "(no summary)"}
"""

    user_prompt = f"""Here are {len(local_articles)} local K-12 education news stories from this week:

{articles_text}

---

Identify up to {max_themes} major THEMES that connect multiple US stories. For each theme:

1. Group 2-4 related stories together (US states only - skip any Canadian/international stories)
2. Write a synthesized blurb (2-3 sentences) that weaves them together
3. The blurb should name specific US states/districts as evidence

IMPORTANT: Only include US states (e.g., Texas, California, New York).
Do NOT include Canadian provinces (Ontario, British Columbia) or other countries.

Format your response EXACTLY like this:

THEME 1: [Short theme title, 3-5 words]
ARTICLES: [comma-separated article numbers]
STATES: [comma-separated US states only]
BLURB: [2-3 sentence synthesis that ties the stories together, mentioning specific US locations]

THEME 2: [Short theme title, 3-5 words]
ARTICLES: [comma-separated article numbers]
STATES: [comma-separated US states only]
BLURB: [2-3 sentence synthesis]

If there aren't enough related US stories to form {max_themes} themes, just return fewer themes.
If stories are too disparate to theme or are mostly non-US, return NONE.

Example output:
THEME 1: School Choice Momentum
ARTICLES: 1, 4, 7
STATES: Texas, Florida, Ohio
BLURB: School choice legislation is gaining traction across multiple states this week. Texas advanced its voucher bill through committee, while Florida expanded its existing program to include more students. Ohio districts are preparing for enrollment shifts as their new open-enrollment policy takes effect.
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=THEME_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response_text = response.content[0].text
        themes = parse_themes_response(response_text)

        return themes

    except Exception as e:
        print(f"  Error clustering local themes: {e}")
        return []


def parse_themes_response(text: str) -> list[dict]:
    """Parse Claude's theme response into structured data."""
    themes = []

    if "NONE" in text.upper() and len(text.strip()) < 50:
        return []

    # Split by THEME markers
    theme_blocks = []
    current_block = []

    for line in text.strip().split("\n"):
        if line.strip().upper().startswith("THEME") and ":" in line:
            if current_block:
                theme_blocks.append("\n".join(current_block))
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        theme_blocks.append("\n".join(current_block))

    # Parse each theme block
    for block in theme_blocks:
        theme = {
            "theme_title": "",
            "blurb": "",
            "article_indices": [],
            "states_mentioned": []
        }

        lines = block.strip().split("\n")
        current_field = None
        current_content = []

        for line in lines:
            line_upper = line.upper().strip()

            if line_upper.startswith("THEME") and ":" in line:
                # Extract theme title
                parts = line.split(":", 1)
                if len(parts) > 1:
                    theme["theme_title"] = parts[1].strip()

            elif line_upper.startswith("ARTICLES:"):
                if current_field == "blurb" and current_content:
                    theme["blurb"] = " ".join(current_content).strip()
                    current_content = []

                # Parse article numbers
                parts = line.split(":", 1)
                if len(parts) > 1:
                    numbers = parts[1].strip()
                    theme["article_indices"] = [
                        int(n.strip()) - 1  # Convert to 0-indexed
                        for n in numbers.split(",")
                        if n.strip().isdigit()
                    ]
                current_field = None

            elif line_upper.startswith("STATES:"):
                # Parse states
                parts = line.split(":", 1)
                if len(parts) > 1:
                    states = parts[1].strip()
                    theme["states_mentioned"] = [
                        s.strip() for s in states.split(",") if s.strip()
                    ]
                current_field = None

            elif line_upper.startswith("BLURB:"):
                current_field = "blurb"
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    current_content = [parts[1].strip()]
                else:
                    current_content = []

            elif current_field == "blurb" and line.strip():
                current_content.append(line.strip())

        # Capture final blurb content
        if current_field == "blurb" and current_content:
            theme["blurb"] = " ".join(current_content).strip()

        # Filter to US-only states
        theme["states_mentioned"] = filter_us_states(theme["states_mentioned"])

        # Only add themes with actual content and at least one US state
        if theme["theme_title"] and theme["blurb"] and theme["states_mentioned"]:
            themes.append(theme)

    return themes


def format_local_spotlight(themes: list[dict], local_articles: list[dict] = None) -> str:
    """
    Format local themes into the LOCAL SPOTLIGHT section for the newsletter.

    Args:
        themes: List of theme dicts from cluster_local_stories
        local_articles: Optional list of original articles (for reference)

    Returns:
        Formatted markdown string for the LOCAL SPOTLIGHT section
    """
    if not themes:
        return ""

    output = """---

**LOCAL SPOTLIGHT**

"""

    for i, theme in enumerate(themes):
        title = theme.get("theme_title", "Local News")
        blurb = theme.get("blurb", "")
        states = theme.get("states_mentioned", [])

        # Format states as location tag
        location_tag = ""
        if states:
            location_tag = f" ({', '.join(states[:3])})"

        output += f"""**{title}**{location_tag}

{blurb}

"""

    return output.rstrip() + "\n"


if __name__ == "__main__":
    # Test with sample local articles
    test_articles = [
        {
            "title": "Texas Senate Advances School Voucher Bill",
            "source": "Texas Tribune",
            "local_reason": "local_domain:tribune",
            "summary": "The Texas Senate passed a voucher bill that would provide $8,000 per student for private school tuition."
        },
        {
            "title": "Florida Expands School Choice Program",
            "source": "Miami Herald",
            "local_reason": "local_domain:herald",
            "summary": "Florida's expanded voucher program will now cover families earning up to 400% of the poverty line."
        },
        {
            "title": "Ohio Districts Brace for Open Enrollment Impact",
            "source": "Cleveland Plain Dealer",
            "local_reason": "local_domain:plain dealer",
            "summary": "Ohio school districts are preparing for student transfers under the new open-enrollment policy."
        },
        {
            "title": "California District Announces Hiring Freeze",
            "source": "Sacramento Bee",
            "local_reason": "local_domain:bee",
            "summary": "Sacramento Unified announces a hiring freeze amid budget shortfall projections."
        },
    ]

    print("Testing local theme clustering...")
    themes = cluster_local_stories(test_articles, max_themes=2)

    if themes:
        print(f"\nFound {len(themes)} themes:")
        for theme in themes:
            print(f"\n  Theme: {theme['theme_title']}")
            print(f"  States: {', '.join(theme['states_mentioned'])}")
            print(f"  Articles: {theme['article_indices']}")
            print(f"  Blurb: {theme['blurb'][:100]}...")

        print("\n" + "="*40)
        print(format_local_spotlight(themes))
    else:
        print("No themes found")
