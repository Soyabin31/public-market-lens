from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}


def normalize_text(value: str | None) -> str:
    """
    Normalize whitespace while preserving the actual text.
    """
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value.strip(),
    )


def canonicalize_url(url: str) -> str:
    """
    Remove common tracking parameters and normalize the URL.

    This is intentionally conservative.
    We do not attempt aggressive URL rewriting because
    different URL paths can represent different articles.
    """
    if not url:
        raise ValueError("Article URL cannot be empty.")

    parsed = urlsplit(url.strip())

    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid article URL: {url}")

    query_parameters = parse_qsl(
        parsed.query,
        keep_blank_values=True,
    )

    filtered_parameters = [
        (key, value)
        for key, value in query_parameters
        if key.lower() not in TRACKING_PARAMETERS
    ]

    normalized_query = urlencode(
        filtered_parameters,
        doseq=True,
    )

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            normalized_query,
            "",
        )
    )


def build_content_hash(
        title: str,
        summary: str | None,
) -> str:
    """
    Generate a SHA-256 hash from normalized article content.

    The hash is intentionally based on textual content rather
    than the URL because multiple URLs may point to the same
    underlying article.
    """
    normalized_title = normalize_text(title)
    normalized_summary = normalize_text(summary)

    content = (
            normalized_title
            + "\n"
            + normalized_summary
    )

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def build_article_identity(
        canonical_url: str,
        content_hash: str,
) -> str:
    """
    Generate the stable article identity used by Market Lens.
    """
    value = (
        f"{canonical_url}|"
        f"{content_hash}"
    )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()