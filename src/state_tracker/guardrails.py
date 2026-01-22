"""
Guardrails and verification for 50-State Topic Tracker.

Responsibilities:
- Extract and verify numbers/statistics against source articles
- Find [REPORTED] and [VERIFY:] flags for editor review
- Build clean source list with tier information
- Check for policy claims that need primary source backing
"""

import re


def extract_numbers_from_text(text: str) -> list[dict]:
    """
    Extract numbers and statistics from text.

    Args:
        text: Text to search

    Returns:
        List of dicts with number, context, and position
    """
    numbers = []

    # Patterns for various number formats
    patterns = [
        # Percentages: 45%, 45 percent
        (r'(\d+(?:\.\d+)?)\s*(?:%|percent)', 'percentage'),
        # Dollar amounts: $1.5 million, $500,000
        (r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|billion|thousand)?', 'dollar'),
        # Plain numbers with context: 15 states, 200 districts
        (r'(\d+(?:,\d{3})*)\s+(?:states?|districts?|schools?|students?|teachers?)', 'count'),
        # Ratios and fractions: 1 in 5, one-third
        (r'(\d+)\s+(?:in|out of)\s+(\d+)', 'ratio'),
        # Year references: 2024, 2025
        (r'\b(20\d{2})\b', 'year'),
    ]

    for pattern, num_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Get context (surrounding 50 chars)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end]

            numbers.append({
                "value": match.group(0),
                "type": num_type,
                "context": context.strip(),
                "position": match.start()
            })

    return numbers


def find_number_in_articles(number_value: str, articles: list[dict]) -> dict:
    """
    Check if a number appears in any source article.

    Args:
        number_value: The number string to find
        articles: List of article dicts with content

    Returns:
        Dict with verification status and source if found
    """
    # Normalize number for comparison
    normalized = re.sub(r'[,\s]', '', number_value.lower())

    for article in articles:
        # Check title
        title = article.get("title", "").lower()
        if normalized in re.sub(r'[,\s]', '', title):
            return {
                "verified": True,
                "source": article.get("source", ""),
                "url": article.get("resolved_url", article.get("url", ""))
            }

        # Check summary
        summary = article.get("summary", "").lower()
        if normalized in re.sub(r'[,\s]', '', summary):
            return {
                "verified": True,
                "source": article.get("source", ""),
                "url": article.get("resolved_url", article.get("url", ""))
            }

        # Check full content if available
        content = article.get("full_content", "").lower()
        if content and normalized in re.sub(r'[,\s]', '', content):
            return {
                "verified": True,
                "source": article.get("source", ""),
                "url": article.get("resolved_url", article.get("url", ""))
            }

        # Check metadata data points
        meta = article.get("metadata", {})
        for data_point in meta.get("key_data_points", []):
            if normalized in re.sub(r'[,\s]', '', data_point.lower()):
                return {
                    "verified": True,
                    "source": article.get("source", ""),
                    "url": article.get("resolved_url", article.get("url", ""))
                }

    return {"verified": False, "source": None, "url": None}


def extract_flags(synthesis: dict) -> list[dict]:
    """
    Extract [REPORTED] and [VERIFY:] flags from synthesis for editor review.

    Args:
        synthesis: Synthesis dict with article sections

    Returns:
        List of flag dicts with type, section, claim, and recommendation
    """
    flags = []

    for section_name, content in synthesis.items():
        if section_name.startswith("_") or not isinstance(content, str):
            continue

        # Find [REPORTED] flags
        reported_pattern = r'\[REPORTED\]\s*([^.\n]+[.\n]?)'
        for match in re.finditer(reported_pattern, content, re.IGNORECASE):
            flags.append({
                "type": "unverified",
                "section": section_name,
                "claim": match.group(1).strip(),
                "recommendation": "Verify with primary source before publishing"
            })

        # Find [VERIFY: reason] flags
        verify_pattern = r'\[VERIFY:\s*([^\]]+)\]'
        for match in re.finditer(verify_pattern, content, re.IGNORECASE):
            flags.append({
                "type": "needs_verification",
                "section": section_name,
                "reason": match.group(1).strip(),
                "recommendation": "Editor should confirm this inference"
            })

    return flags


def verify_synthesis_numbers(synthesis: dict, articles: list[dict]) -> dict:
    """
    Verify that numbers in synthesis appear in source articles.

    Args:
        synthesis: Synthesis dict with article sections
        articles: Source articles

    Returns:
        Dict with verification results
    """
    results = {
        "verified_count": 0,
        "unverified_count": 0,
        "verified_claims": [],
        "unverified_claims": []
    }

    # Combine all synthesis text
    all_text = ""
    for section_name, content in synthesis.items():
        if isinstance(content, str):
            all_text += f" {content}"

    # Extract numbers
    numbers = extract_numbers_from_text(all_text)

    # Verify each number
    for num_info in numbers:
        # Skip year references (2024, 2025) - these are usually valid
        if num_info["type"] == "year":
            continue

        verification = find_number_in_articles(num_info["value"], articles)

        if verification["verified"]:
            results["verified_count"] += 1
            results["verified_claims"].append({
                "number": num_info["value"],
                "context": num_info["context"],
                "source": verification["source"],
                "url": verification["url"]
            })
        else:
            results["unverified_count"] += 1
            results["unverified_claims"].append({
                "number": num_info["value"],
                "context": num_info["context"],
                "note": "Could not verify in source articles"
            })

    return results


def verify_and_flag(synthesis: dict, articles: list[dict]) -> dict:
    """
    Full verification pipeline.

    Args:
        synthesis: Synthesis dict with article sections
        articles: Source articles with metadata

    Returns:
        Verification results dict
    """
    # Extract flags from synthesis
    flags = extract_flags(synthesis)

    # Verify numbers
    number_verification = verify_synthesis_numbers(synthesis, articles)

    # Count Tier A vs other sources
    tier_counts = {"A": 0, "B": 0, "unknown": 0, "C": 0}
    for article in articles:
        tier = article.get("source_tier", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    return {
        "flags_for_review": flags,
        "flag_count": len(flags),
        "number_verification": number_verification,
        "tier_distribution": tier_counts,
        "primary_source_count": tier_counts.get("A", 0),
        "needs_attention": len(flags) > 0 or number_verification["unverified_count"] > 2
    }


def clean_synthesis_for_output(synthesis: dict) -> dict:
    """
    Clean synthesis for final output.

    Optionally removes [REPORTED] and [VERIFY:] markers if desired,
    or keeps them for transparency.

    Args:
        synthesis: Synthesis dict

    Returns:
        Cleaned synthesis dict
    """
    # For now, keep markers for editor transparency
    # Could optionally strip them here if desired
    return synthesis


def generate_editor_notes(verification: dict) -> str:
    """
    Generate editor notes based on verification results.

    Args:
        verification: Results from verify_and_flag()

    Returns:
        Formatted editor notes string
    """
    notes = []

    # Flag summary
    if verification.get("flags_for_review"):
        flag_count = len(verification["flags_for_review"])
        notes.append(f"**{flag_count} item(s) flagged for review**")

        for flag in verification["flags_for_review"][:3]:
            flag_type = flag.get("type", "")
            if flag_type == "unverified":
                notes.append(f"- [REPORTED] in {flag.get('section', 'unknown')}: {flag.get('claim', '')[:50]}...")
            elif flag_type == "needs_verification":
                notes.append(f"- [VERIFY] in {flag.get('section', 'unknown')}: {flag.get('reason', '')}")

    # Number verification
    num_verify = verification.get("number_verification", {})
    if num_verify.get("unverified_count", 0) > 0:
        notes.append(f"\n**{num_verify['unverified_count']} statistic(s) could not be verified against sources**")

    # Source tier summary
    tier_dist = verification.get("tier_distribution", {})
    primary_count = tier_dist.get("A", 0)
    total = sum(tier_dist.values())
    if total > 0:
        notes.append(f"\n**Sources**: {primary_count}/{total} from primary sources (Tier A)")

    if not notes:
        notes.append("No items flagged for review. All statistics verified.")

    return "\n".join(notes)
