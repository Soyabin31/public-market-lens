from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from marketlens.news.models import NewsArticle


class NewsProvider(ABC):
    """
    Abstract interface for news providers.

    Examples of implementations:

        RSSNewsProvider
        GDELTNewsProvider
        NewsAPIProvider
        OfficialFeedProvider
        FuturePaidProvider

    The rest of Market Lens must not depend on the
    provider-specific implementation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Provider identifier.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def source_type(self) -> str:
        """
        Provider type, for example RSS, GDELT, API.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch(
            self,
            start_time: datetime,
            end_time: datetime,
    ) -> list[NewsArticle]:
        """
        Fetch normalized articles for the requested period.
        """
        raise NotImplementedError