"""
Article scraping module using Firecrawl API with free fallback.
Extracts full text content from article URLs.
"""

import os
import re
import time
from typing import Optional
import requests
from bs4 import BeautifulSoup
from firecrawl import FirecrawlApp
from dotenv import load_dotenv

load_dotenv(override=True)

# Rate limit: Firecrawl free tier is 10 req/min
MIN_ARTICLE_CHARACTERS = 500
MIN_ARTICLE_WORDS = 80

SCRAPE_DELAY_SECONDS = 7  # ~8-9 requests per minute to stay safe


def get_firecrawl_client() -> FirecrawlApp:
    """Initialize Firecrawl client."""
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY not found in environment")
    return FirecrawlApp(api_key=api_key)


_FALLBACK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_STRIP_TAGS = ["nav", "footer", "header", "aside", "script", "style", "noscript",
               "iframe", "form", "button", "svg", "figure", "figcaption"]


def _scrape_with_requests(url: str) -> dict:
    """Free fallback scraper using requests + BeautifulSoup."""
    result = {"url": url, "content": None, "title": None, "success": False, "error": None}

    try:
        resp = requests.get(url, headers=_FALLBACK_HEADERS, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else ""

        # Remove noisy elements
        for tag_name in _STRIP_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Try <article> first, then <main>, then largest <div> with paragraphs
        body = soup.find("article") or soup.find("main")
        if not body:
            # Find div with the most <p> tags as a proxy for article content
            candidates = soup.find_all("div")
            if candidates:
                body = max(candidates, key=lambda d: len(d.find_all("p")))

        if not body:
            body = soup.body or soup

        # Extract text from paragraphs for cleaner output
        paragraphs = body.find_all("p")
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

        if has_usable_content(text):
            result["content"] = text
            result["success"] = True
        else:
            result["error"] = f"Insufficient content extracted ({len(text)} chars)"

    except Exception as e:
        result["error"] = str(e)

    return result


def scrape_article(url: str, client: Optional[FirecrawlApp] = None) -> dict:
    """
    Scrape full content from an article URL.

    Args:
        url: Article URL to scrape
        client: Optional Firecrawl client (creates one if not provided)

    Returns:
        Dict with 'content', 'title', 'url', 'success', 'error'
    """
    result = {
        "url": url,
        "content": None,
        "title": None,
        "success": False,
        "error": None
    }

    try:
        if client is None:
            client = get_firecrawl_client()
        # Scrape with Firecrawl (v2 API)
        response = client.scrape(
            url,
            formats=["markdown"],
            only_main_content=True
        )

        # Handle response - could be dict or object with various structures
        markdown_content = None
        title_content = ""

        # Try to extract markdown from various response formats
        if hasattr(response, "markdown"):
            markdown_content = response.markdown
        elif isinstance(response, dict) and "markdown" in response:
            markdown_content = response.get("markdown")

        # Try to extract title from metadata
        if hasattr(response, "metadata"):
            metadata = response.metadata
            if hasattr(metadata, "title"):
                title_content = metadata.title or ""
            elif isinstance(metadata, dict):
                title_content = metadata.get("title", "")
        elif isinstance(response, dict) and "metadata" in response:
            title_content = response.get("metadata", {}).get("title", "")

        if has_usable_content(markdown_content):
            result["content"] = markdown_content
            result["title"] = title_content
            result["success"] = True
        else:
            result["error"] = "Insufficient article content returned"

    except Exception as e:
        result["error"] = str(e)

    # Fallback: try free scraper if Firecrawl failed
    if not result["success"]:
        firecrawl_error = result["error"]
        print(f"    Firecrawl failed ({firecrawl_error[:40] if firecrawl_error else 'unknown'}), trying fallback scraper...")
        fallback = _scrape_with_requests(url)
        if fallback["success"]:
            fallback["scrape_method"] = "fallback"
            print(f"    Fallback succeeded")
            return fallback
        else:
            print(f"    Fallback also failed: {fallback['error']}")
            result["error"] = f"Firecrawl: {firecrawl_error}; Fallback: {fallback['error']}"
    else:
        result["scrape_method"] = "firecrawl"

    return result


def scrape_articles(articles: list[dict], max_articles: int = 20) -> list[dict]:
    """
    Scrape full content for a list of articles.

    Args:
        articles: List of article dicts with 'url' key
        max_articles: Maximum number of articles to scrape

    Returns:
        Articles with 'full_content' added
    """
    # Import here to avoid circular dependency
    from src.feeds import resolve_google_news_url

    try:
        client = get_firecrawl_client()
    except ValueError:
        client = None

    # Limit to max_articles
    to_scrape = articles[:max_articles]

    print(f"Scraping {len(to_scrape)} articles with Firecrawl...")
    print(f"  (Rate limited to ~{60 // SCRAPE_DELAY_SECONDS} req/min, this will take ~{len(to_scrape) * SCRAPE_DELAY_SECONDS // 60} minutes)")

    success_count = 0
    fail_count = 0

    for i, article in enumerate(to_scrape):
        url = article.get("url", "")
        print(f"  [{i+1}/{len(to_scrape)}] Scraping: {article.get('title', url)[:50]}...")

        if not url:
            article["full_content"] = None
            article["scrape_error"] = "No URL"
            fail_count += 1
            continue

        # Resolve Google News redirect URLs to actual article URLs
        resolved_url = resolve_google_news_url(url)
        if resolved_url != url:
            print(f"    Resolved to: {resolved_url[:60]}...")
            article["resolved_url"] = resolved_url
        else:
            resolved_url = url

        result = scrape_article(resolved_url, client)

        if result["success"]:
            article["full_content"] = result["content"]
            article["scraped_title"] = result.get("title", "")
            article["scrape_error"] = None
            success_count += 1
        else:
            article["full_content"] = None
            article["scrape_error"] = result["error"]
            fail_count += 1
            print(f"    Failed: {result['error']}")

        # Rate limiting delay (skip on last article)
        if i < len(to_scrape) - 1:
            time.sleep(SCRAPE_DELAY_SECONDS)

    print(f"Scraping complete: {success_count} succeeded, {fail_count} failed")

    return to_scrape


def has_usable_content(content: str) -> bool:
    """Reject missing text and short excerpts before generating factual summaries."""
    if not isinstance(content, str):
        return False
    text = BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
    return len(text) >= MIN_ARTICLE_CHARACTERS and len(text.split()) >= MIN_ARTICLE_WORDS


def get_content_for_summary(article: dict) -> str:
    """Require substantive scraped text; RSS headlines are not source evidence."""
    content = article.get("full_content")
    if not has_usable_content(content):
        raise ValueError("Insufficient article text; refusing to summarize an RSS snippet")
    return content[:8000]


if __name__ == "__main__":
    # Test scraping (requires FIRECRAWL_API_KEY)
    test_url = "https://www.edweek.org/technology/artificial-intelligence"

    print(f"Testing scrape of: {test_url}")
    result = scrape_article(test_url)

    if result["success"]:
        print(f"Success! Title: {result['title']}")
        print(f"Content preview: {result['content'][:500]}...")
    else:
        print(f"Failed: {result['error']}")
