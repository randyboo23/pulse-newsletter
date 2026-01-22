"""
Two-pass deduplication for 50-State Topic Tracker.

Pass 1: Exact/near-exact removal (URL, title similarity)
Pass 2: Semantic clustering using sentence-transformers

Keeps 1 "core" article + 1-2 "incremental detail" articles per cluster.
"""

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

# Lazy load sentence-transformers to avoid import overhead
_embedding_model = None


def get_embedding_model():
    """Lazy load the sentence transformer model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("  Loading embedding model...")
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            print("  Warning: sentence-transformers not installed, skipping semantic dedup")
            return None
    return _embedding_model


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    if not title:
        return ""
    # Lowercase, remove punctuation, strip whitespace
    normalized = title.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = ' '.join(normalized.split())
    return normalized


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # Remove www, trailing slashes, common tracking params
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{domain}{path}".lower()
    except Exception:
        return url.lower()


def title_similarity(title1: str, title2: str) -> float:
    """Calculate title similarity using SequenceMatcher."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    if not norm1 or not norm2:
        return 0.0
    return SequenceMatcher(None, norm1, norm2).ratio()


def dedup_pass1_exact(articles: list[dict], similarity_threshold: float = 0.85) -> list[dict]:
    """
    Pass 1: Remove exact/near-exact duplicates.

    Uses URL matching and title similarity.
    Prefers higher-tier sources when duplicates found.

    Args:
        articles: List of article dicts
        similarity_threshold: Title similarity threshold (default 0.85)

    Returns:
        Deduplicated list
    """
    if len(articles) <= 1:
        return articles

    seen_urls = set()
    unique_articles = []
    duplicates_found = 0

    # Sort by tier so better sources come first
    tier_order = {"A": 0, "B": 1, "unknown": 2, "C": 3}
    sorted_articles = sorted(
        articles,
        key=lambda a: (
            tier_order.get(a.get("source_tier", "unknown"), 2),
            -a.get("total_score", 0)
        )
    )

    for article in sorted_articles:
        url = article.get("resolved_url", article.get("url", ""))
        norm_url = normalize_url(url)
        title = article.get("title", "")

        # Check URL duplicate
        if norm_url and norm_url in seen_urls:
            duplicates_found += 1
            continue

        # Check title similarity against existing
        is_duplicate = False
        for existing in unique_articles:
            existing_title = existing.get("title", "")
            if title_similarity(title, existing_title) >= similarity_threshold:
                is_duplicate = True
                duplicates_found += 1
                break

        if not is_duplicate:
            unique_articles.append(article)
            if norm_url:
                seen_urls.add(norm_url)

    if duplicates_found > 0:
        print(f"  Pass 1: Removed {duplicates_found} exact/near duplicates")

    return unique_articles


def dedup_pass2_semantic(
    articles: list[dict],
    similarity_threshold: float = 0.75,
    max_per_cluster: int = 3
) -> list[dict]:
    """
    Pass 2: Semantic clustering using embeddings.

    Groups similar stories and keeps best representatives per cluster.

    Args:
        articles: List of article dicts (after pass 1)
        similarity_threshold: Cosine similarity threshold for clustering
        max_per_cluster: Max articles to keep per cluster

    Returns:
        Deduplicated list with cluster info
    """
    if len(articles) <= 2:
        return articles

    model = get_embedding_model()
    if model is None:
        # sentence-transformers not available, skip this pass
        return articles

    try:
        import numpy as np
        from sklearn.cluster import AgglomerativeClustering
    except ImportError:
        print("  Warning: sklearn not available, skipping semantic clustering")
        return articles

    # Build text representations for embedding
    texts = []
    for article in articles:
        title = article.get("title", "")
        summary = article.get("summary", "")[:200]  # Limit summary length
        texts.append(f"{title}. {summary}")

    # Generate embeddings
    print("  Pass 2: Generating embeddings...")
    embeddings = model.encode(texts, show_progress_bar=False)

    # Cluster using agglomerative clustering with cosine distance
    # Convert similarity threshold to distance threshold
    distance_threshold = 1 - similarity_threshold

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric='cosine',
        linkage='average'
    )

    labels = clustering.fit_predict(embeddings)
    n_clusters = len(set(labels))
    print(f"  Pass 2: Found {n_clusters} clusters from {len(articles)} articles")

    # Process each cluster
    result = []
    for cluster_id in set(labels):
        cluster_indices = [i for i, l in enumerate(labels) if l == cluster_id]
        cluster_articles = [articles[i] for i in cluster_indices]

        # Select representatives from this cluster
        selected = select_cluster_representatives(cluster_articles, max_per_cluster)
        result.extend(selected)

    removed = len(articles) - len(result)
    if removed > 0:
        print(f"  Pass 2: Consolidated {removed} articles via clustering")

    return result


def select_cluster_representatives(
    cluster: list[dict],
    max_per_cluster: int = 3
) -> list[dict]:
    """
    Select best articles from a cluster.

    Strategy:
    1. Core article: Highest tier + highest score
    2. Incremental 1-2: Different state coverage OR unique details

    Args:
        cluster: List of articles in the same cluster
        max_per_cluster: Maximum articles to keep

    Returns:
        Selected articles with is_incremental flag
    """
    if len(cluster) <= max_per_cluster:
        return cluster

    # Sort by (tier priority, score)
    tier_order = {"A": 0, "B": 1, "unknown": 2, "C": 3}
    sorted_cluster = sorted(
        cluster,
        key=lambda a: (
            tier_order.get(a.get("source_tier", "unknown"), 2),
            -a.get("total_score", 0)
        )
    )

    # Always take the core (best) article
    selected = [sorted_cluster[0]]
    core_states = set(sorted_cluster[0].get("states_mentioned", []))

    # Add incremental articles with state diversity
    for article in sorted_cluster[1:]:
        if len(selected) >= max_per_cluster:
            break

        article_states = set(article.get("states_mentioned", []))

        # Keep if it covers new states
        if article_states - core_states:
            article["is_incremental"] = True
            selected.append(article)
            # Update core states to include new ones
            core_states.update(article_states)

    # If we still have room and haven't filled, take next best
    for article in sorted_cluster[1:]:
        if len(selected) >= max_per_cluster:
            break
        if article not in selected:
            article["is_incremental"] = True
            selected.append(article)

    return selected


def deduplicate_state_articles(articles: list[dict]) -> list[dict]:
    """
    Full two-pass deduplication pipeline.

    Args:
        articles: List of article dicts

    Returns:
        Deduplicated list
    """
    if not articles:
        return []

    # Pass 1: Exact/near-exact
    deduped = dedup_pass1_exact(articles)

    # Pass 2: Semantic clustering
    deduped = dedup_pass2_semantic(deduped)

    return deduped
