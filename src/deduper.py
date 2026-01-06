"""
Deduplication module for removing duplicate articles.
Uses title similarity and URL matching.
"""

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    # Lowercase
    title = title.lower()
    # Remove punctuation
    title = re.sub(r'[^\w\s]', '', title)
    # Remove extra whitespace
    title = ' '.join(title.split())
    return title


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    parsed = urlparse(url)
    # Remove www prefix
    domain = parsed.netloc.replace("www.", "")
    # Get path without trailing slash
    path = parsed.path.rstrip("/")
    return f"{domain}{path}".lower()


def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity ratio between two titles."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    return SequenceMatcher(None, norm1, norm2).ratio()


def is_duplicate(article1: dict, article2: dict, threshold: float = 0.85) -> bool:
    """
    Check if two articles are duplicates.

    Args:
        article1: First article dict
        article2: Second article dict
        threshold: Similarity threshold (0-1) for title matching

    Returns:
        True if articles are duplicates
    """
    # Check URL match first (fastest)
    url1 = normalize_url(article1.get("url", ""))
    url2 = normalize_url(article2.get("url", ""))

    if url1 and url2 and url1 == url2:
        return True

    # Check title similarity
    title1 = article1.get("title", "")
    title2 = article2.get("title", "")

    if title1 and title2:
        similarity = title_similarity(title1, title2)
        if similarity >= threshold:
            return True

    return False


def deduplicate_articles(articles: list[dict], threshold: float = 0.85) -> list[dict]:
    """
    Remove duplicate articles from list.

    Keeps the first occurrence of each unique article.
    Prefers articles from trusted sources when duplicates are found.

    Args:
        articles: List of article dicts
        threshold: Similarity threshold for title matching

    Returns:
        Deduplicated list of articles
    """
    if not articles:
        return []

    # Trusted sources get priority
    trusted_domains = {
        "k12dive.com", "the74million.org", "chalkbeat.org",
        "edsurge.com", "hechingerreport.org", "edutopia.org",
        "kqed.org", "edsource.org", "eschoolnews.com"
    }

    def source_priority(article: dict) -> int:
        """Higher number = higher priority."""
        url = article.get("url", "")
        domain = urlparse(url).netloc.replace("www.", "")
        return 1 if domain in trusted_domains else 0

    # Sort by priority (trusted sources first)
    sorted_articles = sorted(articles, key=source_priority, reverse=True)

    unique = []
    seen_urls = set()
    seen_titles = []

    for article in sorted_articles:
        url = normalize_url(article.get("url", ""))
        title = article.get("title", "")

        # Skip if URL already seen
        if url and url in seen_urls:
            continue

        # Check title similarity against seen titles
        is_dup = False
        for seen_title in seen_titles:
            if title_similarity(title, seen_title) >= threshold:
                is_dup = True
                break

        if not is_dup:
            unique.append(article)
            if url:
                seen_urls.add(url)
            if title:
                seen_titles.append(title)

    return unique


def dedupe_stats(original: list[dict], deduped: list[dict]) -> dict:
    """Generate deduplication statistics."""
    return {
        "original_count": len(original),
        "deduped_count": len(deduped),
        "removed": len(original) - len(deduped),
        "removal_rate": f"{((len(original) - len(deduped)) / len(original) * 100):.1f}%" if original else "0%"
    }


if __name__ == "__main__":
    # Test deduplication
    test_articles = [
        {"title": "Schools Embrace AI Tools for Learning", "url": "https://example.com/ai-schools", "source": "EdWeek"},
        {"title": "Schools Embrace AI Tools for Learning!", "url": "https://other.com/ai-learning", "source": "Blog"},
        {"title": "New Education Policy Announced", "url": "https://example.com/policy", "source": "K12Dive"},
        {"title": "Completely Different Article", "url": "https://example.com/different", "source": "EdSurge"},
    ]

    unique = deduplicate_articles(test_articles)
    stats = dedupe_stats(test_articles, unique)

    print(f"Deduplication results:")
    print(f"  Original: {stats['original_count']}")
    print(f"  Unique: {stats['deduped_count']}")
    print(f"  Removed: {stats['removed']} ({stats['removal_rate']})")
