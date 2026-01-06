"""
RSS feed fetching module using feedparser.
Fetches articles from Google News RSS feeds for configured queries.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.queries import get_all_feed_urls


def resolve_google_news_url(google_url: str) -> str:
    """
    Resolve Google News redirect URL to actual article URL.

    Google News RSS provides URLs like:
    https://news.google.com/rss/articles/CBMi...

    These contain encoded article URLs that we decode.
    """
    if "news.google.com" not in google_url:
        return google_url

    try:
        from googlenewsdecoder import new_decoderv1
        decoded = new_decoderv1(google_url, interval=0.5)
        if decoded and decoded.get("decoded_url"):
            return decoded["decoded_url"]
        return google_url
    except Exception as e:
        # Fallback: try HTTP redirect
        try:
            response = requests.head(
                google_url,
                allow_redirects=True,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PulseK12/1.0)"}
            )
            if response.url != google_url:
                return response.url
        except Exception:
            pass
        return google_url


def parse_pub_date(entry: dict) -> Optional[datetime]:
    """Parse publication date from feed entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    return None


def extract_source_url(entry: dict) -> str:
    """
    Extract the actual source URL from Google News entry.
    Google News wraps URLs, so we try to get the original.
    """
    # Google News stores original URL in link
    return entry.get("link", "")


def extract_source_name(entry: dict) -> str:
    """Extract the source publication name."""
    # Google News includes source in the title suffix or source field
    if hasattr(entry, "source") and entry.source:
        return entry.source.get("title", "Unknown")
    # Fallback: try to parse from title (often formatted as "Headline - Source")
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1]
    return "Unknown"


def fetch_single_feed(feed_config: dict) -> list[dict]:
    """
    Fetch articles from a single RSS feed.

    Args:
        feed_config: Dict with 'url', 'name', 'category_hint'

    Returns:
        List of article dicts
    """
    articles = []

    try:
        feed = feedparser.parse(feed_config["url"])

        if feed.bozo and not feed.entries:
            print(f"  Warning: Feed error for {feed_config['name']}: {feed.bozo_exception}")
            return articles

        for entry in feed.entries:
            pub_date = parse_pub_date(entry)

            # Clean title (remove source suffix if present)
            title = entry.get("title", "")
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]

            article = {
                "title": title,
                "url": extract_source_url(entry),
                "source": extract_source_name(entry),
                "published": pub_date,
                "summary": entry.get("summary", ""),
                "category_hint": feed_config.get("category_hint"),
                "feed_name": feed_config["name"]
            }
            articles.append(article)

    except Exception as e:
        print(f"  Error fetching {feed_config['name']}: {e}")

    return articles


def fetch_all_feeds(days_back: int = 7) -> list[dict]:
    """
    Fetch articles from all configured RSS feeds.

    Args:
        days_back: Number of days to look back

    Returns:
        List of all article dicts from all feeds
    """
    all_articles = []
    feed_urls = get_all_feed_urls(days_back)

    print(f"Fetching from {len(feed_urls)} RSS feeds...")

    for feed_config in feed_urls:
        print(f"  Fetching: {feed_config['name']}")
        articles = fetch_single_feed(feed_config)
        print(f"    Found {len(articles)} articles")
        all_articles.extend(articles)

        # Small delay to be nice to Google
        time.sleep(0.5)

    print(f"Total articles fetched: {len(all_articles)}")
    return all_articles


def filter_by_date(articles: list[dict], days_back: int = 7) -> list[dict]:
    """Filter articles to only those within the date range."""
    cutoff = datetime.now() - timedelta(days=days_back)
    filtered = []

    for article in articles:
        pub_date = article.get("published")
        if pub_date is None:
            # Include articles without dates (can't verify)
            filtered.append(article)
        elif pub_date >= cutoff:
            filtered.append(article)

    return filtered


if __name__ == "__main__":
    # Test the feed fetching
    articles = fetch_all_feeds(days_back=7)
    articles = filter_by_date(articles, days_back=7)
    print(f"\nFiltered to {len(articles)} articles from last 7 days")

    for i, article in enumerate(articles[:5]):
        print(f"\n{i+1}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   URL: {article['url'][:80]}...")
