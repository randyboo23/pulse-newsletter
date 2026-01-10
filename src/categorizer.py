"""
Article categorization and balanced selection module.
Uses keyword matching to classify articles and ensures category diversity.
"""

import re
import sys
import os
from collections import defaultdict
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.categories import CATEGORIES, CATEGORY_BALANCE, get_all_categories

# Trusted education news sources (prioritized)
TRUSTED_EDUCATION_DOMAINS = {
    "k12dive.com", "the74million.org", "chalkbeat.org", "edsurge.com",
    "hechingerreport.org", "edutopia.org", "kqed.org", "edsource.org",
    "ednc.org", "eschoolnews.com", "edtechmagazine.com", "districtadministration.com",
    "edweek.org", "educationweek.org", "nwea.org", "rand.org",
    "brookings.edu", "edtechinnovationhub.com", "iste.org"
}

# Domains to always exclude (spam, off-topic, low-quality)
BLOCKED_DOMAINS = {
    # Spam/tabloid
    "bollywoodhelpline.com", "bollywood", "cricket", "sports",
    "celebrity", "entertainment", "gossip", "horoscope",
    # Non-US / off-topic regional
    "indiantelevision.com", "philenews.com", "in-cyprus",
    "leadership.ng", "qatar-tribune.com", "britannica.com",
    # General news not focused on K-12
    "usaherald.com", "gritdaily.com", "demandsage.com",
    # Press release mills
    "prweb.com", "prnewswire.com", "businesswire.com"
}

# Source names to block (matched against RSS source field - case insensitive)
BLOCKED_SOURCES = {
    # Non-US regional
    "philenews", "in-cyprus", "leadership newspapers", "leadership.ng",
    "qatar tribune", "indian television", "indiantelevision",
    # Off-topic
    "usa herald", "usaherald", "grit daily", "gritdaily",
    "bollywood", "cricket", "sports",
    # Press releases
    "pr newswire", "prnewswire", "business wire", "businesswire", "prweb",
    # Low quality
    "demandsage", "herald-mail"  # press release aggregator
}

# Authority tiers for source quality scoring
AUTHORITY_TIERS = {
    "tier1": {  # +0.3 - Premier K-12 education outlets
        "k12dive.com", "the74million.org", "chalkbeat.org",
        "edweek.org", "educationweek.org", "hechingerreport.org"
    },
    "tier2": {  # +0.2 - Respected education media
        "edsurge.com", "edutopia.org", "edsource.org",
        "eschoolnews.com", "ednc.org", "districtadministration.com"
    },
    "tier3": {  # +0.1 - Research/policy organizations
        "brookings.edu", "rand.org", "nwea.org", "iste.org",
        "edtechmagazine.com", "edtechinnovationhub.com"
    }
}

# Patterns that indicate local/regional news (conservative - avoid false positives)
# Only patterns that clearly indicate local newspapers/stations
LOCAL_DOMAIN_PATTERNS = {
    # Clear local newspaper patterns
    "patch.com", "gazette", "herald", "tribune",
    # Local TV patterns (with call letters)
    "khou", "kxan", "wfaa", "wkyc", "wcnc", "wpxi", "wsoc", "wxia",
    # Specific local news indicators
    "daily", "county", "weekly", "local"
}

# US states for detecting local stories in titles
US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming"
}

# US state abbreviations
US_STATE_ABBREVS = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy"
}

# International indicators - filter these out (US-only newsletter)
INTERNATIONAL_COUNTRIES = {
    "canada", "canadian", "uk", "britain", "british", "england", "scotland", "wales",
    "ireland", "irish", "australia", "australian", "new zealand",
    "france", "french", "germany", "german", "spain", "spanish", "italy", "italian",
    "netherlands", "dutch", "belgium", "swiss", "switzerland", "austria", "austrian",
    "sweden", "swedish", "norway", "norwegian", "denmark", "danish", "finland", "finnish",
    "poland", "polish", "czech", "hungary", "hungarian", "romania", "romanian",
    "russia", "russian", "ukraine", "ukrainian", "china", "chinese", "japan", "japanese",
    "korea", "korean", "india", "indian", "singapore", "hong kong", "taiwan",
    "mexico", "mexican", "brazil", "brazilian", "argentina", "chile", "colombia",
    "israel", "israeli", "saudi", "emirates", "dubai", "qatar",
    "africa", "african", "nigeria", "kenya", "south africa",
    "europe", "european", "eu", "asia", "asian", "pacific"
}

INTERNATIONAL_DOMAINS = {
    ".ca", ".uk", ".co.uk", ".au", ".nz", ".ie", ".fr", ".de", ".es", ".it",
    ".nl", ".be", ".ch", ".at", ".se", ".no", ".dk", ".fi", ".pl", ".cz",
    ".ru", ".cn", ".jp", ".kr", ".in", ".sg", ".hk", ".tw", ".mx", ".br",
    ".eu", "euronews", "bbc.com", "theguardian.com", "telegraph.co.uk",
    "cbc.ca", "globalnews.ca", "abc.net.au", "stuff.co.nz",
    "98fm.com", "rte.ie", "independent.ie"  # Irish outlets
}

# Core education keywords - article must contain at least one
EDUCATION_KEYWORDS = {
    "school", "student", "teacher", "education", "classroom", "learning",
    "k-12", "k12", "district", "curriculum", "literacy", "academic",
    "principal", "superintendent", "edtech", "instruction", "pedagogy",
    "college", "university", "graduate", "enrollment", "tuition",
    "homework", "assessment", "test score", "achievement", "grade level"
}

# Patterns for roundup/listicle articles to filter out
# These compile heavy aggregation articles that don't tell a single story
ROUNDUP_PATTERNS = [
    r'\btop\s+\d+\b',           # "Top 10 EdTech Stories"
    r'\bbest\s+\d+\b',          # "Best 5 AI Tools"
    r'\b\d+\s+best\b',          # "10 Best Learning Apps"
    r'\b\d+\s+top\b',           # "5 Top Trends"
    r'\bweekly\s+roundup\b',    # "Weekly Roundup"
    r'\bweek\s+in\s+review\b',  # "Week in Review"
    r'\bmonthly\s+roundup\b',   # "Monthly Roundup"
    r'\bstories\s+of\s+the\s+(week|month|year)\b',  # "Stories of the Week"
    r'\bnews\s+roundup\b',      # "News Roundup"
    r'\bedtech\s+digest\b',     # "EdTech Digest"
    r'\bthis\s+week\s+in\b',    # "This Week in Education"
    r'\bwhat\s+we.re\s+reading\b',  # "What We're Reading"
    r'\blinks\s+of\s+the\s+(week|day)\b',  # "Links of the Week"
    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(roundup|recap|review)\b',
]


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").lower()
        return domain
    except Exception:
        return ""


def is_roundup_article(article: dict) -> bool:
    """
    Check if article is a roundup/listicle that aggregates multiple stories.

    These are filtered out because they:
    - Don't tell a single coherent story
    - Often duplicate content we'd get from primary sources
    - Don't fit the newsletter format well

    Args:
        article: Article dict with 'title'

    Returns:
        True if article appears to be a roundup/listicle
    """
    title = article.get("title", "").lower()

    for pattern in ROUNDUP_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    return False


def is_blocked_source(source_name: str) -> bool:
    """Check if source name matches any blocked source."""
    source_lower = source_name.lower()
    for blocked in BLOCKED_SOURCES:
        if blocked in source_lower:
            return True
    return False


def is_international_story(article: dict) -> tuple[bool, str]:
    """
    Detect if article is about international (non-US) education.

    We want US-only content for this newsletter.

    Args:
        article: Article dict

    Returns:
        Tuple of (is_international: bool, reason: str)
    """
    url = article.get("resolved_url", article.get("url", ""))
    domain = get_domain(url)
    title = article.get("title", "").lower()
    source = article.get("source", "").lower()

    # Check for international domains
    for intl_domain in INTERNATIONAL_DOMAINS:
        if intl_domain in domain:
            return True, f"intl_domain:{intl_domain}"

    # Check for international country mentions in title
    for country in INTERNATIONAL_COUNTRIES:
        if re.search(rf'\b{country}\b', title):
            return True, f"intl_country:{country}"

    # Check source name for international indicators
    for country in INTERNATIONAL_COUNTRIES:
        if country in source:
            return True, f"intl_source:{country}"

    return False, ""


def get_authority_score(article: dict) -> float:
    """
    Calculate authority score based on source domain tier.

    Args:
        article: Article dict with 'url' or 'resolved_url'

    Returns:
        Score: 0.3 (tier1), 0.2 (tier2), 0.1 (tier3), 0.0 (other)
    """
    url = article.get("resolved_url", article.get("url", ""))
    domain = get_domain(url)

    if not domain:
        return 0.0

    # Check each tier
    for tier_domain in AUTHORITY_TIERS["tier1"]:
        if tier_domain in domain:
            return 0.3

    for tier_domain in AUTHORITY_TIERS["tier2"]:
        if tier_domain in domain:
            return 0.2

    for tier_domain in AUTHORITY_TIERS["tier3"]:
        if tier_domain in domain:
            return 0.1

    return 0.0


def get_trending_score(article: dict) -> float:
    """
    Calculate trending score based on feed appearances.

    Articles appearing in multiple feeds are likely more significant.

    Args:
        article: Article dict with 'feed_appearance_count'

    Returns:
        Score: 0.0-0.3 based on feed appearance count
    """
    count = article.get("feed_appearance_count", 1)

    # 1 feed = 0.0, 2 feeds = 0.1, 3 feeds = 0.2, 4+ feeds = 0.3
    if count >= 4:
        return 0.3
    elif count >= 3:
        return 0.2
    elif count >= 2:
        return 0.1
    return 0.0


def is_local_story(article: dict) -> tuple[bool, str]:
    """
    Detect if article is a local/regional story.

    Detection strategy (conservative - only flag clearly local stories):
    1. Authority sources are NEVER local (they cover national news)
    2. Local domain patterns (daily, herald, tribune, etc.) → LOCAL
    3. State names in title are only flagged if source looks local (not for general news)

    Args:
        article: Article dict

    Returns:
        Tuple of (is_local: bool, reason: str)
    """
    url = article.get("resolved_url", article.get("url", ""))
    domain = get_domain(url)
    title = article.get("title", "").lower()
    source = article.get("source", "").lower()

    # Skip if from authority source (they cover national news)
    authority = get_authority_score(article)
    if authority > 0:
        return False, ""

    # National news domains - never flag as local
    national_domains = [
        "nytimes", "washingtonpost", "usatoday", "wsj", "reuters", "ap",
        "cnn", "foxnews", "nbcnews", "cbsnews", "abcnews", "npr.org",
        "politico", "thehill", "axios", "vox", "slate", "forbes"
    ]
    if any(nat in domain for nat in national_domains):
        return False, ""

    # Check domain patterns that indicate local news
    has_local_domain = False
    local_pattern_match = ""
    for pattern in LOCAL_DOMAIN_PATTERNS:
        if pattern in domain or pattern in source:
            has_local_domain = True
            local_pattern_match = pattern
            break

    # If domain is clearly local, flag it
    if has_local_domain:
        return True, f"local_domain:{local_pattern_match}"

    # For non-local-looking domains, only flag if it's a government/state-specific source
    # (state legislature sites, local government, etc.)
    government_patterns = [".gov", "senate", "assembly", "legislature", "state."]
    is_government_source = any(gov in domain for gov in government_patterns)

    if is_government_source:
        # Government source mentioning state → likely state-specific news
        for state in US_STATES:
            if re.search(rf'\b{state}\b', title) or state in domain:
                return True, f"government_state:{state}"

    # Don't flag state names in titles from general news sources
    # State policy stories can be nationally relevant
    return False, ""


def is_relevant_article(article: dict) -> bool:
    """
    Check if article is relevant to US K-12 education.

    Returns True if:
    - From a trusted education domain, OR
    - Contains education keywords in title/summary
    - AND is about US education (not international)

    Returns False if:
    - From a blocked domain or source
    - Contains no education keywords
    - Is about international (non-US) education
    - Is a roundup/listicle article
    """
    # Check blocked source names first (works without URL resolution)
    source = article.get("source", "")
    if is_blocked_source(source):
        return False

    # Check for roundup/listicle articles
    if is_roundup_article(article):
        return False

    # Check for international content (US-only newsletter)
    is_intl, intl_reason = is_international_story(article)
    if is_intl:
        return False

    url = article.get("url", "") or article.get("resolved_url", "")
    domain = get_domain(url)

    # Check blocked domains
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return False

    # Trusted domains always pass
    if domain in TRUSTED_EDUCATION_DOMAINS:
        return True

    # Check for education keywords in content
    text = " ".join([
        article.get("title", ""),
        article.get("summary", ""),
        source
    ]).lower()

    for keyword in EDUCATION_KEYWORDS:
        if keyword in text:
            return True

    return False


def filter_relevant_articles(articles: list[dict]) -> list[dict]:
    """
    Filter articles to only those relevant to K-12 education.

    Args:
        articles: List of article dicts

    Returns:
        Filtered list of relevant articles
    """
    relevant = []
    removed = 0

    for article in articles:
        if is_relevant_article(article):
            relevant.append(article)
        else:
            removed += 1

    if removed > 0:
        print(f"  Filtered out {removed} non-education articles")

    return relevant


def calculate_quality_score(article: dict, category_score: float) -> dict:
    """
    Calculate composite quality score for an article.

    Score breakdown:
    - category_score: 0.0-1.0 (keyword matching)
    - authority_score: 0.0-0.3 (source tier)
    - trending_score: 0.0-0.3 (feed appearances)
    - local_penalty: 0.0 or -0.2 (if local story)

    Args:
        article: Article dict
        category_score: Score from category keyword matching

    Returns:
        Dict with score breakdown and total
    """
    authority = get_authority_score(article)
    trending = get_trending_score(article)
    is_local, local_reason = is_local_story(article)
    local_penalty = -0.2 if is_local else 0.0

    total = category_score + authority + trending + local_penalty

    return {
        "category_score": category_score,
        "authority_score": authority,
        "trending_score": trending,
        "local_penalty": local_penalty,
        "is_local": is_local,
        "local_reason": local_reason,
        "total_score": total
    }


def calculate_category_score(article: dict, category_id: str) -> float:
    """
    Calculate how well an article matches a category.

    Args:
        article: Article dict with 'title', 'summary', 'source'
        category_id: Category ID to score against

    Returns:
        Score (0-1) indicating match strength
    """
    category = CATEGORIES.get(category_id)
    if not category:
        return 0.0

    keywords = category.get("keywords", [])
    if not keywords:
        return 0.0

    # Combine searchable text
    text = " ".join([
        article.get("title", ""),
        article.get("summary", ""),
        article.get("source", "")
    ]).lower()

    # Count keyword matches
    matches = 0
    for keyword in keywords:
        if keyword.lower() in text:
            matches += 1

    # Normalize score
    return min(matches / 3, 1.0)  # Cap at 1.0, 3 matches = full score


def classify_article(article: dict) -> tuple[str, float]:
    """
    Classify an article into the best-matching category.

    Args:
        article: Article dict

    Returns:
        Tuple of (category_id, confidence_score)
    """
    # If article has a category hint from the feed, use it as a tiebreaker
    hint = article.get("category_hint")

    best_category = None
    best_score = 0.0

    for category_id in get_all_categories():
        score = calculate_category_score(article, category_id)

        # Boost score slightly if matches the feed's category hint
        if hint and category_id == hint:
            score += 0.1

        if score > best_score:
            best_score = score
            best_category = category_id

    # Default to 'teaching' if no good match (most general category)
    if best_category is None or best_score < 0.1:
        best_category = "teaching"
        best_score = 0.1

    return best_category, best_score


def classify_all_articles(articles: list[dict]) -> list[dict]:
    """
    Classify all articles and add category info with composite quality scoring.

    Args:
        articles: List of article dicts

    Returns:
        Articles with category info and quality scores added:
        - category: Best matching category ID
        - category_score: Keyword match score (0-1)
        - authority_score: Source tier score (0-0.3)
        - trending_score: Feed appearance score (0-0.3)
        - is_local: Whether article is local news
        - total_score: Composite quality score
    """
    for article in articles:
        # Get category classification
        category_id, cat_score = classify_article(article)
        article["category"] = category_id

        # Calculate composite quality score
        quality = calculate_quality_score(article, cat_score)

        # Store all score components on article
        article["category_score"] = quality["category_score"]
        article["authority_score"] = quality["authority_score"]
        article["trending_score"] = quality["trending_score"]
        article["local_penalty"] = quality["local_penalty"]
        article["is_local"] = quality["is_local"]
        article["local_reason"] = quality["local_reason"]
        article["total_score"] = quality["total_score"]

    return articles


def select_balanced_menu(articles: list[dict], target_count: int = 20, max_local: int = 3) -> list[dict]:
    """
    Select a balanced set of articles across all categories.

    Strategy:
    1. Ensure minimum representation per category (2 each), prefer non-local
    2. Fill remaining slots with highest-scoring articles (respecting max per category)
    3. Enforce local story limit (swap out excess locals for non-locals)

    Args:
        articles: Classified articles with 'category', 'total_score', 'is_local'
        target_count: Target number of articles to select
        max_local: Maximum number of local stories allowed

    Returns:
        Balanced selection of articles
    """
    min_per_cat = CATEGORY_BALANCE["min_per_category"]
    max_per_cat = CATEGORY_BALANCE["max_per_category"]

    # Group articles by category
    by_category = defaultdict(list)
    for article in articles:
        by_category[article.get("category", "teaching")].append(article)

    # Sort each category by total_score (descending), with non-local preferred
    for cat in by_category:
        by_category[cat].sort(
            key=lambda x: (not x.get("is_local", False), x.get("total_score", 0)),
            reverse=True
        )

    selected = []
    category_counts = defaultdict(int)
    local_count = 0

    # Phase 1: Guarantee minimum per category (prefer non-local)
    for category_id in get_all_categories():
        cat_articles = by_category.get(category_id, [])
        added = 0
        for article in cat_articles:
            if added >= min_per_cat:
                break
            if article not in selected:
                # Skip locals if we're at the limit and have other options
                if article.get("is_local", False) and local_count >= max_local:
                    # Check if there are non-local alternatives in this category
                    non_locals = [a for a in cat_articles if not a.get("is_local", False) and a not in selected]
                    if non_locals:
                        continue  # Skip this local, we'll get a non-local
                selected.append(article)
                category_counts[category_id] += 1
                if article.get("is_local", False):
                    local_count += 1
                added += 1

    # Phase 2: Fill remaining slots with best articles (respecting max per category and local limit)
    remaining_slots = target_count - len(selected)

    if remaining_slots > 0:
        # Create pool of unselected articles, sorted by total_score
        unselected = [a for a in articles if a not in selected]
        unselected.sort(key=lambda x: x.get("total_score", 0), reverse=True)

        for article in unselected:
            if len(selected) >= target_count:
                break

            cat = article.get("category", "teaching")
            is_local = article.get("is_local", False)

            # Skip if category is full
            if category_counts[cat] >= max_per_cat:
                continue

            # Skip if local and we're at the local limit
            if is_local and local_count >= max_local:
                continue

            selected.append(article)
            category_counts[cat] += 1
            if is_local:
                local_count += 1

    # Phase 3: If we still have too many locals (from Phase 1 minimums), swap them out
    if local_count > max_local:
        # Find locals that could be swapped
        local_articles = [a for a in selected if a.get("is_local", False)]
        non_local_pool = [a for a in articles if a not in selected and not a.get("is_local", False)]
        non_local_pool.sort(key=lambda x: x.get("total_score", 0), reverse=True)

        excess = local_count - max_local
        swapped = 0

        for local_article in sorted(local_articles, key=lambda x: x.get("total_score", 0)):
            if swapped >= excess:
                break
            if not non_local_pool:
                break

            # Find a non-local replacement from same category if possible
            cat = local_article.get("category", "teaching")
            replacement = None

            # Try same category first
            for candidate in non_local_pool:
                if candidate.get("category") == cat and category_counts[cat] <= max_per_cat:
                    replacement = candidate
                    break

            # If no same-category replacement, take best available
            if not replacement:
                for candidate in non_local_pool:
                    cand_cat = candidate.get("category", "teaching")
                    if category_counts[cand_cat] < max_per_cat:
                        replacement = candidate
                        break

            if replacement:
                # Swap
                selected.remove(local_article)
                selected.append(replacement)
                non_local_pool.remove(replacement)
                category_counts[local_article.get("category")] -= 1
                category_counts[replacement.get("category")] += 1
                swapped += 1
                local_count -= 1

    # Log local story count
    final_local_count = sum(1 for a in selected if a.get("is_local", False))
    if final_local_count > 0:
        print(f"  Local stories in selection: {final_local_count}/{max_local} max")

    return selected


def get_category_distribution(articles: list[dict]) -> dict:
    """Get count of articles per category."""
    distribution = defaultdict(int)
    for article in articles:
        cat = article.get("category", "unknown")
        distribution[cat] += 1
    return dict(distribution)


def print_distribution(articles: list[dict]) -> None:
    """Print category distribution for debugging."""
    dist = get_category_distribution(articles)
    print("\nCategory Distribution:")
    for cat_id, count in sorted(dist.items()):
        cat = CATEGORIES.get(cat_id, {})
        emoji = cat.get("emoji", "📰")
        name = cat.get("name", cat_id)
        print(f"  {emoji} {name}: {count}")


if __name__ == "__main__":
    # Test classification
    test_articles = [
        {"title": "AI Tutoring Tools Transform Classrooms", "summary": "New artificial intelligence apps help students learn"},
        {"title": "State Passes New Education Funding Bill", "summary": "Legislature approves budget increase for schools"},
        {"title": "Teachers Report Burnout at Record Levels", "summary": "Survey shows staff retention crisis"},
        {"title": "District Implements MTSS Framework", "summary": "Multi-tiered support system shows results"},
    ]

    classified = classify_all_articles(test_articles)

    for article in classified:
        cat = CATEGORIES.get(article["category"], {})
        print(f"{cat.get('emoji')} [{article['category']}] {article['title']}")
        print(f"   Score: {article['category_score']:.2f}")
