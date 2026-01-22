"""
Source tiering for 50-State Topic Tracker.

Classifies article sources into tiers:
- Tier A: Primary/official sources (government, named reporter journalism, state DOE)
- Tier B: Secondary sources (regional outlets, policy orgs, local TV with documents)
- Tier C: Blocked (content farms, SEO rewrites, press release mills)

Includes 2-hop verification rule for policy claims.
"""

import re
from urllib.parse import urlparse

from .config import SOURCE_TIERS, DOMAIN_STATE_MAP


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "").lower()
    except Exception:
        return ""


def is_tier_a_source(domain: str, url: str = "") -> tuple[bool, str]:
    """
    Check if source is Tier A (primary/best).

    Tier A includes:
    - Government domains (.gov, legislature, etc.)
    - Named reporter local journalism
    - State education specialty outlets

    Args:
        domain: Domain string
        url: Full URL (for path checks)

    Returns:
        Tuple of (is_tier_a, reason)
    """
    tier_a = SOURCE_TIERS["tier_a"]

    # Check government patterns
    for pattern in tier_a.get("gov_patterns", []):
        if pattern in domain:
            return True, f"gov_pattern:{pattern}"

    # Check local journalism outlets
    for outlet in tier_a.get("local_journalism", []):
        if outlet in domain:
            return True, f"local_journalism:{outlet}"

    # Check state education outlets
    for outlet in tier_a.get("state_education", []):
        if outlet in domain:
            return True, f"state_education:{outlet}"

    # Check domain-to-state mapping (these are quality local outlets)
    if domain in DOMAIN_STATE_MAP:
        return True, f"mapped_local:{domain}"

    return False, ""


def is_tier_b_source(domain: str) -> tuple[bool, str]:
    """
    Check if source is Tier B (good secondary).

    Tier B includes:
    - Regional education outlets
    - Policy organizations
    - Local TV stations

    Args:
        domain: Domain string

    Returns:
        Tuple of (is_tier_b, reason)
    """
    tier_b = SOURCE_TIERS["tier_b"]

    # Check regional/policy domains
    for outlet in tier_b.get("domains", []):
        if outlet in domain:
            return True, f"tier_b_outlet:{outlet}"

    # Check local TV patterns
    for pattern in tier_b.get("local_tv_patterns", []):
        if pattern in domain:
            return True, f"local_tv:{pattern}"

    return False, ""


def is_tier_c_blocked(domain: str, url: str = "") -> tuple[bool, str]:
    """
    Check if source is Tier C (blocked).

    Tier C includes:
    - Content farms and aggregators
    - Press release mills
    - SEO rewrite sites

    Args:
        domain: Domain string
        url: Full URL (for path checks)

    Returns:
        Tuple of (is_blocked, reason)
    """
    tier_c = SOURCE_TIERS["tier_c_blocked"]

    # Check blocked domains
    for blocked in tier_c.get("domains", []):
        if blocked in domain:
            return True, f"blocked_domain:{blocked}"

    # Check URL patterns
    url_lower = url.lower() if url else ""
    for pattern in tier_c.get("patterns", []):
        if pattern in url_lower:
            return True, f"blocked_pattern:{pattern}"

    return False, ""


def classify_source_tier(article: dict) -> tuple[str, float, str]:
    """
    Classify an article's source into a tier.

    Args:
        article: Article dict with url, resolved_url, source

    Returns:
        Tuple of (tier: 'A'|'B'|'C'|'unknown', confidence: float, reason: str)
    """
    url = article.get("resolved_url", article.get("url", ""))
    domain = get_domain(url)
    source_name = article.get("source", "").lower()

    if not domain:
        return "unknown", 0.3, "no_domain"

    # Check Tier C first (blocked)
    is_blocked, block_reason = is_tier_c_blocked(domain, url)
    if is_blocked:
        return "C", 0.0, block_reason

    # Check source name for press release indicators
    pr_indicators = ["pr newswire", "business wire", "prweb", "globe newswire"]
    for indicator in pr_indicators:
        if indicator in source_name:
            return "C", 0.0, f"pr_source:{indicator}"

    # Check Tier A
    is_a, a_reason = is_tier_a_source(domain, url)
    if is_a:
        return "A", 0.95, a_reason

    # Check Tier B
    is_b, b_reason = is_tier_b_source(domain)
    if is_b:
        return "B", 0.75, b_reason

    # Check source name for local newspaper patterns
    # Helps when URLs are unresolved (news.google.com)
    local_paper_patterns = [
        "tribune", "times", "post", "herald", "chronicle",
        "journal", "gazette", "democrat", "republican",
        "daily", "sentinel", "observer", "register"
    ]
    for pattern in local_paper_patterns:
        if pattern in source_name and "pr newswire" not in source_name:
            return "B", 0.6, f"local_newspaper_name:{pattern}"

    # Default: unknown tier, moderate confidence
    # These are sources we don't have explicit mappings for
    return "unknown", 0.5, f"unmapped:{domain}"


def filter_tier_c(articles: list[dict]) -> list[dict]:
    """
    Filter out Tier C (blocked) articles.

    Args:
        articles: List of articles with source_tier set

    Returns:
        Filtered list excluding Tier C
    """
    filtered = []
    removed = 0

    for article in articles:
        tier = article.get("source_tier", "unknown")
        if tier == "C":
            removed += 1
            continue
        filtered.append(article)

    if removed > 0:
        print(f"  Filtered out {removed} Tier C articles")

    return filtered


def check_for_primary_source_link(content: str) -> list[str]:
    """
    Extract links from article content that might be primary sources.

    Used for 2-hop verification: if a Tier B article links to a
    government or primary source, the claim is more trustworthy.

    Args:
        content: Article content (markdown)

    Returns:
        List of URLs that appear to be primary sources
    """
    if not content:
        return []

    # Find markdown links: [text](url)
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    matches = re.findall(link_pattern, content)

    # Find plain URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    plain_urls = re.findall(url_pattern, content)

    all_urls = [url for _, url in matches] + plain_urls

    # Filter to likely primary sources
    primary_sources = []
    for url in all_urls:
        domain = get_domain(url)
        is_a, _ = is_tier_a_source(domain, url)
        if is_a:
            primary_sources.append(url)

    return primary_sources


def verify_policy_claim_sources(article: dict) -> dict:
    """
    Verify that policy claims have primary source backing.

    Implements the 2-hop rule: policy claims should either be from
    a Tier A source, or link to a Tier A source within the content.

    Args:
        article: Article dict with full_content (if scraped)

    Returns:
        Dict with verification status and details
    """
    tier = article.get("source_tier", "unknown")
    content = article.get("full_content", "")

    result = {
        "tier": tier,
        "has_primary_backing": False,
        "primary_sources_found": [],
        "verification_note": ""
    }

    # Tier A is already primary
    if tier == "A":
        result["has_primary_backing"] = True
        result["verification_note"] = "Source is primary (Tier A)"
        return result

    # For other tiers, check for links to primary sources
    if content:
        primary_links = check_for_primary_source_link(content)
        if primary_links:
            result["has_primary_backing"] = True
            result["primary_sources_found"] = primary_links[:3]  # Limit to 3
            result["verification_note"] = f"Links to {len(primary_links)} primary source(s)"
            return result

    # No primary backing found
    result["verification_note"] = "No primary source link found - mark as [REPORTED]"
    return result
