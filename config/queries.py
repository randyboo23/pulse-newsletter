"""
Google News RSS search queries for PulseK12 newsletter.
6 query groups covering all K-12 topics, with trusted site filters.
"""

# Trusted K-12 education news sources
TRUSTED_SITES = [
    "k12dive.com",
    "the74million.org",
    "chalkbeat.org",
    "edsurge.com",
    "hechingerreport.org",
    "edutopia.org",
    "kqed.org",
    "edsource.org",
    "ednc.org",
    "eschoolnews.com",
    "edtechmagazine.com",
    "districtadministration.com",
]

# Build site filter string for Google News
SITE_FILTER = " OR ".join([f"site:{site}" for site in TRUSTED_SITES])

# 6 Search query groups - each targets different topic clusters
SEARCH_QUERIES = [
    {
        "id": "ai_edtech",
        "name": "AI & EdTech",
        "query": '"AI in education" OR "artificial intelligence schools" OR "edtech" OR "education technology trends"',
        "category_hint": "ai_edtech"
    },
    {
        "id": "policy",
        "name": "Policy & Legislation",
        "query": '"K-12 policy" OR "education legislation" OR "school funding" OR "education budget"',
        "category_hint": "policy"
    },
    {
        "id": "teaching",
        "name": "Teaching & Instruction",
        "query": '"instructional strategies" OR "teacher professional development" OR "learning gaps" OR "math instruction" OR "literacy"',
        "category_hint": "teaching"
    },
    {
        "id": "safety_privacy",
        "name": "Safety & Privacy",
        "query": '"school safety technology" OR "student data privacy" OR "education cybersecurity" OR "student behavior policy"',
        "category_hint": "safety"
    },
    {
        "id": "wellness",
        "name": "Student Wellness",
        "query": '"chronic absenteeism" OR "student mental health" OR "MTSS" OR "school attendance" OR "SEL"',
        "category_hint": "wellness"
    },
    {
        "id": "general_k12",
        "name": "General K-12",
        "query": f'"K-12 education" OR "public schools" OR "school districts" ({SITE_FILTER})',
        "category_hint": None  # Will be classified by content
    }
]


def build_google_news_rss_url(query: str, days_back: int = 7) -> str:
    """
    Build a Google News RSS URL for the given query.

    Args:
        query: Search query string
        days_back: Number of days to look back (default 7)

    Returns:
        Google News RSS feed URL
    """
    import urllib.parse

    # Google News RSS base URL
    base_url = "https://news.google.com/rss/search"

    # Add time filter (when:7d for last 7 days)
    full_query = f"{query} when:{days_back}d"

    # Encode and build URL
    params = urllib.parse.urlencode({
        "q": full_query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    })

    return f"{base_url}?{params}"


def get_all_feed_urls(days_back: int = 7) -> list[dict]:
    """
    Get all RSS feed URLs for the configured queries.

    Returns:
        List of dicts with 'url', 'name', and 'category_hint'
    """
    feeds = []
    for query_config in SEARCH_QUERIES:
        feeds.append({
            "url": build_google_news_rss_url(query_config["query"], days_back),
            "name": query_config["name"],
            "category_hint": query_config["category_hint"]
        })
    return feeds
