"""
Editor feedback tracking and adaptive scoring utilities.

This module records weekly editor behavior and converts it into
recency-weighted ranking signals for article selection.
"""

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from config.categories import CATEGORIES


DATA_DIR = Path(__file__).parent.parent / "data"
FEEDBACK_FILE = DATA_DIR / "editor_feedback.json"

# User-curated URL submissions are intentionally weighted higher.
SIGNAL_WEIGHTS = {
    "menu_selection": 1.0,
    "submitted_url": 3.0,
}

# Recency/boost controls
HALF_LIFE_DAYS = 42.0
MAX_EVENT_AGE_DAYS = 180
DOMAIN_BOOST_FACTOR = 0.04
CATEGORY_BOOST_FACTOR = 0.02
TOKEN_BOOST_FACTOR = 0.01
MAX_DOMAIN_BOOST = 0.18
MAX_CATEGORY_BOOST = 0.10
MAX_TOKEN_BOOST = 0.08
MAX_TOTAL_BOOST = 0.30
MAX_TOKENS_PER_EVENT = 16
MAX_PROFILE_TOKENS = 300

TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9']{2,}")
TOKEN_STOPWORDS = {
    "about", "after", "again", "also", "among", "around", "because", "before",
    "being", "below", "between", "both", "district", "during", "each", "education", "from",
    "have", "having", "here", "into", "its", "k12", "many", "more", "most",
    "news", "over", "same", "school", "schools", "some", "such", "that", "their",
    "there", "these", "they", "this", "those", "through", "under", "very",
    "were", "what", "when", "where", "which", "while", "with", "would"
}


def _utc_now() -> datetime:
    """Get timezone-aware current UTC timestamp."""
    return datetime.now(timezone.utc)


def _default_feedback_data() -> dict:
    """Default feedback file shape."""
    return {
        "version": 1,
        "updated_at": None,
        "events": []
    }


def _normalize_text(value: str) -> str:
    """Normalize text for lenient matching."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _build_category_lookup() -> dict[str, str]:
    """Build category-name/category-id lookup map."""
    lookup = {}
    for category_id, meta in CATEGORIES.items():
        lookup[_normalize_text(category_id)] = category_id
        lookup[_normalize_text(meta.get("name", ""))] = category_id
    return lookup


CATEGORY_LOOKUP = _build_category_lookup()


def normalize_category_id(value: str) -> Optional[str]:
    """
    Convert category labels/ids into canonical category ids.

    Supports ids like "ai_edtech" and labels like "AI & EdTech".
    """
    if not value:
        return None

    if value in CATEGORIES:
        return value

    return CATEGORY_LOOKUP.get(_normalize_text(value))


def extract_domain(url: str) -> str:
    """Extract a normalized domain from URL."""
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().split("@")[-1]
        domain = domain.split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _parse_timestamp(value: str) -> Optional[datetime]:
    """Parse ISO timestamp, returning UTC datetime."""
    if not value:
        return None

    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def extract_signal_tokens(text: str, limit: int = MAX_TOKENS_PER_EVENT) -> list[str]:
    """
    Extract stable preference tokens from summary/title text.

    Returns up to `limit` tokens sorted by frequency then alpha.
    """
    if not text:
        return []

    counts: dict[str, int] = defaultdict(int)
    for raw in TOKEN_PATTERN.findall(text.lower()):
        token = raw.strip("'")
        if token.endswith("'s"):
            token = token[:-2]
        if len(token) < 3 or token in TOKEN_STOPWORDS:
            continue
        counts[token] += 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:limit]]


def load_feedback_data() -> dict:
    """Load feedback events from disk."""
    if not FEEDBACK_FILE.exists():
        return _default_feedback_data()

    try:
        with open(FEEDBACK_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        return _default_feedback_data()

    if not isinstance(data, dict):
        return _default_feedback_data()

    if not isinstance(data.get("events"), list):
        data["events"] = []

    return data


def _save_feedback_data(data: dict) -> None:
    """Persist feedback data to disk."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _prune_old_events(events: list[dict], now: datetime) -> list[dict]:
    """Keep only valid, recent feedback events."""
    cutoff = now - timedelta(days=MAX_EVENT_AGE_DAYS)
    kept = []

    for event in events:
        ts = _parse_timestamp(event.get("timestamp"))
        if not ts:
            continue
        if ts >= cutoff:
            kept.append(event)

    return kept


def record_editor_feedback(
    menu_summaries: list[dict],
    submitted_urls: list[str],
    url_summaries: Optional[list[dict]] = None,
    now: Optional[datetime] = None
) -> dict:
    """
    Record editor interaction signals to improve future ranking.

    Args:
        menu_summaries: Selected menu summary objects
        submitted_urls: URLs sent directly by editor
        url_summaries: On-demand URL summary dicts (headline/summary/url)
        now: Optional timestamp override (UTC)

    Returns:
        Dict with event counts
    """
    now_utc = now or _utc_now()
    data = load_feedback_data()
    events = data.get("events", [])

    menu_events = 0
    url_events = 0

    url_summary_map = {}
    for result in url_summaries or []:
        url = result.get("url", "")
        if url and result.get("success", False):
            url_summary_map[url] = result

    for summary in menu_summaries:
        url = summary.get("source_url") or summary.get("url", "")
        domain = extract_domain(url)
        if not domain:
            continue

        text_blob = " ".join([
            summary.get("headline", ""),
            summary.get("summary", "")
        ])

        category = normalize_category_id(
            summary.get("category")
            or summary.get("category_id")
            or summary.get("category_name")
        )

        events.append({
            "timestamp": now_utc.isoformat(),
            "signal": "menu_selection",
            "weight": SIGNAL_WEIGHTS["menu_selection"],
            "domain": domain,
            "category": category,
            "tokens": extract_signal_tokens(text_blob)
        })
        menu_events += 1

    for url in submitted_urls:
        domain = extract_domain(url)
        if not domain:
            continue

        summary_data = url_summary_map.get(url, {})
        text_blob = " ".join([
            summary_data.get("headline", ""),
            summary_data.get("summary", "")
        ])

        events.append({
            "timestamp": now_utc.isoformat(),
            "signal": "submitted_url",
            "weight": SIGNAL_WEIGHTS["submitted_url"],
            "domain": domain,
            "category": None,
            "tokens": extract_signal_tokens(text_blob)
        })
        url_events += 1

    data["events"] = _prune_old_events(events, now_utc)
    data["updated_at"] = now_utc.isoformat()
    _save_feedback_data(data)

    return {
        "menu_events": menu_events,
        "url_events": url_events,
        "events_added": menu_events + url_events,
        "events_kept": len(data["events"])
    }


def build_feedback_profile(data: dict, now: Optional[datetime] = None) -> dict:
    """
    Build decayed feedback scores for domains/categories.

    Args:
        data: Feedback data with event list
        now: Optional timestamp override (UTC)

    Returns:
        Profile dict used by ranking
    """
    now_utc = now or _utc_now()
    events = data.get("events", []) if isinstance(data, dict) else []

    domain_scores: dict[str, float] = defaultdict(float)
    category_scores: dict[str, float] = defaultdict(float)
    token_scores: dict[str, float] = defaultdict(float)
    valid_events = 0

    for event in events:
        ts = _parse_timestamp(event.get("timestamp"))
        if not ts:
            continue

        age_days = max((now_utc - ts).total_seconds() / 86400.0, 0.0)
        if age_days > MAX_EVENT_AGE_DAYS:
            continue

        weight = float(event.get("weight", SIGNAL_WEIGHTS.get(event.get("signal"), 1.0)))
        decay = math.pow(0.5, age_days / HALF_LIFE_DAYS)
        score = weight * decay

        domain = event.get("domain", "")
        if domain:
            domain_scores[domain] += score

        category_id = normalize_category_id(event.get("category"))
        if category_id:
            category_scores[category_id] += score

        for token in event.get("tokens", []) or []:
            if isinstance(token, str) and token:
                token_scores[token] += score

        valid_events += 1

    ranked_tokens = sorted(
        token_scores.items(),
        key=lambda item: item[1],
        reverse=True
    )[:MAX_PROFILE_TOKENS]

    return {
        "domain_scores": dict(domain_scores),
        "category_scores": dict(category_scores),
        "token_scores": dict(ranked_tokens),
        "event_count": valid_events
    }


def load_feedback_profile(now: Optional[datetime] = None) -> dict:
    """Load and build the feedback profile in one call."""
    data = load_feedback_data()
    return build_feedback_profile(data, now=now)


def get_feedback_boost(article: dict, profile: Optional[dict]) -> tuple[float, str]:
    """
    Compute capped ranking boost from editor feedback.

    Args:
        article: Article dict with URL/category fields
        profile: Built feedback profile

    Returns:
        Tuple of (boost_score, reason_string)
    """
    if not profile:
        return 0.0, ""

    domain_scores = profile.get("domain_scores", {})
    category_scores = profile.get("category_scores", {})
    token_scores = profile.get("token_scores", {})

    resolved_url = article.get("resolved_url") or article.get("url", "")
    domain = extract_domain(resolved_url)
    category_id = normalize_category_id(article.get("category"))
    article_text = " ".join([
        article.get("title", ""),
        article.get("summary", "")
    ])
    article_tokens = extract_signal_tokens(article_text, limit=24)

    domain_score = domain_scores.get(domain, 0.0)
    category_score = category_scores.get(category_id, 0.0) if category_id else 0.0
    token_score = sum(token_scores.get(token, 0.0) for token in article_tokens)

    domain_boost = min(domain_score * DOMAIN_BOOST_FACTOR, MAX_DOMAIN_BOOST)
    category_boost = min(category_score * CATEGORY_BOOST_FACTOR, MAX_CATEGORY_BOOST)
    token_boost = min(token_score * TOKEN_BOOST_FACTOR, MAX_TOKEN_BOOST)
    total_boost = min(domain_boost + category_boost + token_boost, MAX_TOTAL_BOOST)

    reasons = []
    if domain_boost > 0:
        reasons.append(f"domain:{domain}")
    if category_boost > 0 and category_id:
        reasons.append(f"category:{category_id}")
    if token_boost > 0:
        matched = [token for token in article_tokens if token_scores.get(token, 0.0) > 0]
        if matched:
            reasons.append(f"tokens:{','.join(matched[:3])}")

    return total_boost, ",".join(reasons)
