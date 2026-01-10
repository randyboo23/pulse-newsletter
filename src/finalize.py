#!/usr/bin/env python3
"""
Finalize newsletter issue from selected articles.
Takes article numbers from the menu email and generates the final formatted issue.

Usage:
    python3 src/finalize.py 1,3,5,7,9,11
    python3 src/finalize.py "1, 3, 5, 7, 9, 11"
"""

import sys
import os
import json
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
from src.emailer import send_newsletter, get_week_subject

# Path where main.py saves summaries
SUMMARIES_FILE = Path(__file__).parent.parent / "data" / "latest_summaries.json"


def get_anthropic_client() -> anthropic.Anthropic:
    """Initialize Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment")
    return anthropic.Anthropic(api_key=api_key)


def load_summaries() -> dict:
    """
    Load summaries from the last pipeline run.

    Returns:
        Dict with:
        - summaries: List of national article summaries
        - local_themes: List of themed local story clusters
        - local_articles: Original local articles (for reference)
    """
    if not SUMMARIES_FILE.exists():
        raise FileNotFoundError(
            f"No summaries found at {SUMMARIES_FILE}. "
            "Run the main pipeline first to generate the menu."
        )

    with open(SUMMARIES_FILE, "r") as f:
        data = json.load(f)

    return {
        "summaries": data.get("summaries", []),
        "local_themes": data.get("local_themes", []),
        "local_articles": data.get("local_articles", [])
    }


def parse_selection(selection_str: str) -> list[int]:
    """
    Parse user's selection string into list of 1-indexed article numbers.

    Handles formats like:
    - "1,3,5,7"
    - "1, 3, 5, 7"
    - "1 3 5 7"
    """
    # Extract all numbers from the string
    numbers = re.findall(r'\d+', selection_str)
    return [int(n) for n in numbers]


def generate_glance_summary(selected_summaries: list[dict]) -> str:
    """
    Generate "This Week at a Glance" bullet summary using Claude.

    Creates 3-5 bullet points capturing the key themes from selected articles.
    """
    client = get_anthropic_client()

    # Build context from selected articles
    articles_text = ""
    for i, s in enumerate(selected_summaries, 1):
        articles_text += f"{i}. {s.get('headline', 'Untitled')}\n"
        articles_text += f"   {s.get('summary', '')}\n\n"

    prompt = f"""You are writing the "This Week at a Glance" intro for the PulseK12 newsletter.

Here are this week's selected articles:

{articles_text}

Write 3-5 bullet points (using • character) that capture the major themes. IMPORTANT: Each bullet must be 12-15 words MAX. Be punchy and direct. No filler words.

Format:
• Short punchy theme (12-15 words max)
• Another key takeaway (12-15 words max)
• Third theme (12-15 words max)

Do not include any intro text - just the bullets."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()


def get_number_emoji(n: int) -> str:
    """Convert number to keycap emoji (1️⃣, 2️⃣, etc.)."""
    keycaps = {
        1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
        6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟",
        11: "1️⃣1️⃣", 12: "1️⃣2️⃣"
    }
    return keycaps.get(n, f"{n}.")


def format_local_spotlight_final(local_themes: list[dict]) -> str:
    """
    Format local themes into the LOCAL SPOTLIGHT section for the final issue.

    Args:
        local_themes: List of theme dicts from cluster_local_stories

    Returns:
        Formatted markdown string for the LOCAL SPOTLIGHT section
    """
    if not local_themes:
        return ""

    output = """📍 LOCAL SPOTLIGHT

"""

    for theme in local_themes:
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

    output += "———\n\n"
    return output


def format_final_issue(
    selected_summaries: list[dict],
    glance_summary: str,
    local_themes: list[dict] = None
) -> str:
    """
    Format the complete final newsletter issue for Beehiiv copy/paste.

    Args:
        selected_summaries: List of selected national article summaries
        glance_summary: The "This Week at a Glance" bullet points
        local_themes: Optional list of local theme clusters

    Returns:
        Formatted markdown string for the final issue
    """
    today = datetime.now()
    date_str = today.strftime("%B %d, %Y")

    # Header - clean for Beehiiv
    output = f"""THIS WEEK AT A GLANCE

{glance_summary}

———

"""

    # Output articles in order with category headers
    for i, s in enumerate(selected_summaries, 1):
        emoji = s.get("category_emoji", "📰")
        category_name = s.get("category_name", "General").upper()
        headline = s.get("headline", "Untitled")
        url = s.get("source_url", "#")
        summary_text = s.get("summary", "")

        # Format: number emoji + CATEGORY NAME, then headline link, then summary
        output += f"""{get_number_emoji(i)} {category_name}

{emoji} [{headline}]({url})

{summary_text}

———

"""

    # Add LOCAL SPOTLIGHT section if we have themes
    if local_themes:
        output += format_local_spotlight_final(local_themes)

    # Clean ending (no footer needed for Beehiiv - they add their own)
    return output.rstrip() + "\n"


def finalize_issue(selection_str: str, send_email: bool = True) -> dict:
    """
    Generate and optionally email the final newsletter issue.

    Args:
        selection_str: Comma-separated list of article numbers (1-indexed)
        send_email: Whether to send the email

    Returns:
        Dict with results
    """
    print("=" * 60)
    print("PulseK12 Newsletter Finalization")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load summaries and local themes
    print("\n[1/4] Loading summaries...")
    try:
        data = load_summaries()
        all_summaries = data.get("summaries", [])
        local_themes = data.get("local_themes", [])
        print(f"  Loaded {len(all_summaries)} national summaries from last run")
        if local_themes:
            print(f"  Loaded {len(local_themes)} local themes")
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        return {"success": False, "error": str(e)}

    # Parse selection
    print("\n[2/4] Parsing selection...")
    selected_numbers = parse_selection(selection_str)
    print(f"  Selected articles: {selected_numbers}")

    # Get selected summaries (convert 1-indexed to 0-indexed)
    selected_summaries = []
    for num in selected_numbers:
        idx = num - 1
        if 0 <= idx < len(all_summaries):
            selected_summaries.append(all_summaries[idx])
        else:
            print(f"  Warning: Article #{num} not found, skipping")

    if not selected_summaries:
        print("  Error: No valid articles selected")
        return {"success": False, "error": "No valid articles selected"}

    print(f"  Found {len(selected_summaries)} valid selections")

    # Generate glance summary
    print("\n[3/4] Generating 'This Week at a Glance'...")
    glance_summary = generate_glance_summary(selected_summaries)
    print(f"  Generated {len(glance_summary.split('•')) - 1} bullet points")

    # Format final issue (includes local themes automatically)
    print("\n[4/4] Formatting final issue...")
    final_content = format_final_issue(selected_summaries, glance_summary, local_themes)
    print(f"  Final issue: {len(final_content)} characters")
    if local_themes:
        print(f"  Included {len(local_themes)} local spotlight themes")

    # Output or send
    if send_email:
        print("\nSending final issue email...")
        subject = f"PulseK12 Final Issue - {get_week_subject()}"
        result = send_newsletter(final_content, subject=subject)
        if result["success"]:
            print("  Email sent successfully!")
        else:
            print(f"  Email error: {result['error']}")
    else:
        print("\n" + "=" * 60)
        print("FINAL ISSUE PREVIEW")
        print("=" * 60)
        print(final_content)

    print("\n" + "=" * 60)
    print("Finalization Complete!")
    print("=" * 60)

    return {
        "success": True,
        "selected_count": len(selected_summaries),
        "final_content": final_content,
        "glance_summary": glance_summary
    }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Finalize PulseK12 newsletter from selected articles"
    )
    parser.add_argument(
        "selection",
        help="Comma-separated article numbers (e.g., '1,3,5,7,9,11')"
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Preview only, don't send email"
    )

    args = parser.parse_args()

    result = finalize_issue(
        selection_str=args.selection,
        send_email=not args.preview
    )

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
