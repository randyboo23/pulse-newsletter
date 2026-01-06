"""
Article categorization and balanced selection module.
Uses keyword matching to classify articles and ensures category diversity.
"""

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

# Core education keywords - article must contain at least one
EDUCATION_KEYWORDS = {
    "school", "student", "teacher", "education", "classroom", "learning",
    "k-12", "k12", "district", "curriculum", "literacy", "academic",
    "principal", "superintendent", "edtech", "instruction", "pedagogy",
    "college", "university", "graduate", "enrollment", "tuition",
    "homework", "assessment", "test score", "achievement", "grade level"
}


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").lower()
        return domain
    except Exception:
        return ""


def is_blocked_source(source_name: str) -> bool:
    """Check if source name matches any blocked source."""
    source_lower = source_name.lower()
    for blocked in BLOCKED_SOURCES:
        if blocked in source_lower:
            return True
    return False


def is_relevant_article(article: dict) -> bool:
    """
    Check if article is relevant to K-12 education.

    Returns True if:
    - From a trusted education domain, OR
    - Contains education keywords in title/summary

    Returns False if:
    - From a blocked domain or source
    - Contains no education keywords
    """
    # Check blocked source names first (works without URL resolution)
    source = article.get("source", "")
    if is_blocked_source(source):
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
    Classify all articles and add category info.

    Args:
        articles: List of article dicts

    Returns:
        Articles with 'category' and 'category_score' added
    """
    for article in articles:
        category_id, score = classify_article(article)
        article["category"] = category_id
        article["category_score"] = score

    return articles


def select_balanced_menu(articles: list[dict], target_count: int = 20) -> list[dict]:
    """
    Select a balanced set of articles across all categories.

    Strategy:
    1. Ensure minimum representation per category (2 each)
    2. Fill remaining slots with highest-scoring articles
    3. Cap any category at max (4) to prevent dominance

    Args:
        articles: Classified articles with 'category' and 'category_score'
        target_count: Target number of articles to select

    Returns:
        Balanced selection of articles
    """
    min_per_cat = CATEGORY_BALANCE["min_per_category"]
    max_per_cat = CATEGORY_BALANCE["max_per_category"]

    # Group articles by category
    by_category = defaultdict(list)
    for article in articles:
        by_category[article.get("category", "teaching")].append(article)

    # Sort each category by score (descending)
    for cat in by_category:
        by_category[cat].sort(key=lambda x: x.get("category_score", 0), reverse=True)

    selected = []
    category_counts = defaultdict(int)

    # Phase 1: Guarantee minimum per category
    for category_id in get_all_categories():
        cat_articles = by_category.get(category_id, [])
        for article in cat_articles[:min_per_cat]:
            if article not in selected:
                selected.append(article)
                category_counts[category_id] += 1

    # Phase 2: Fill remaining slots with best articles (respecting max)
    remaining_slots = target_count - len(selected)

    if remaining_slots > 0:
        # Create pool of unselected articles, sorted by score
        unselected = [a for a in articles if a not in selected]
        unselected.sort(key=lambda x: x.get("category_score", 0), reverse=True)

        for article in unselected:
            if len(selected) >= target_count:
                break

            cat = article.get("category", "teaching")
            if category_counts[cat] < max_per_cat:
                selected.append(article)
                category_counts[cat] += 1

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
