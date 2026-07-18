"""Shared Anthropic model configuration and health checks."""

import os
from typing import Optional

import anthropic


DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
MIN_COMPLETE_SUMMARIES = 15

_SYSTEMIC_ERROR_MARKERS = (
    "authentication_error",
    "credit balance is too low",
    "invalid x-api-key",
    "not_found_error",
    "plans & billing",
    "permission_error",
)


def get_anthropic_model() -> str:
    """Return the configured Claude model, falling back to the current default."""
    configured_model = os.getenv("ANTHROPIC_MODEL", "").strip()
    return configured_model or DEFAULT_ANTHROPIC_MODEL


def get_minimum_complete_summaries(target_articles: int) -> int:
    """Return the minimum usable summary count for the requested menu size."""
    national_target = min(20, max(0, target_articles))
    return min(MIN_COMPLETE_SUMMARIES, national_target)


def is_systemic_anthropic_error(error: object) -> bool:
    """Identify errors that make additional Claude attempts pointless this run."""
    if isinstance(
        error,
        (
            anthropic.AuthenticationError,
            anthropic.NotFoundError,
            anthropic.PermissionDeniedError,
        ),
    ):
        return True

    message = str(error).lower()
    return any(marker in message for marker in _SYSTEMIC_ERROR_MARKERS)


def extract_anthropic_text(response: object) -> str:
    """Extract text blocks from a Claude response, ignoring thinking blocks."""
    content = getattr(response, "content", [])
    text_parts = [
        block.text.strip()
        for block in content
        if isinstance(getattr(block, "text", None), str) and block.text.strip()
    ]

    if text_parts:
        return "\n".join(text_parts)

    block_types = [
        getattr(block, "type", type(block).__name__)
        for block in content
    ]
    types_label = ", ".join(block_types) if block_types else "none"
    raise ValueError(
        f"Anthropic response contained no text block (blocks: {types_label})"
    )


def preflight_anthropic(
    client: Optional[anthropic.Anthropic] = None,
) -> str:
    """Verify API credentials, credits, and model access with a tiny request."""
    if client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        client = anthropic.Anthropic(api_key=api_key)

    model = get_anthropic_model()
    client.messages.create(
        model=model,
        max_tokens=8,
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )
    return model
