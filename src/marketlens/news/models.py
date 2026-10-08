from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib


@dataclass(frozen=True)
class NewsArticle:
    """
    Normalized internal representation of a news article.

    Provider-specific formats are converted into this model
    before persistence.
    """

    source: str
    source_type: str

    url: str
    canonical_url: str

    title: str
    summary: str | None

    published_at: datetime
    ingested_at: datetime

    content_hash: str

    language: str | None = None
    author: str | None = None

    market: str | None = None
    symbol: str | None = None
    geography: str | None = None
    asset_class: str | None = None
    category: str | None = None

    body: str | None = None
    raw_metadata: str | None = None

    @property
    def article_id(self) -> str:
        """
        Generate a stable article identifier.

        The identity is based on the canonical URL and
        normalized content hash.
        """
        value = (
            f"{self.canonical_url}|"
            f"{self.content_hash}"
        )

        return hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()