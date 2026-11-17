from __future__ import annotations

from abc import ABC, abstractmethod

from phone_scraper.core.normalize import NormalizedPriceRecord


class ParseError(RuntimeError):
    """Raised loudly when expected DOM or JSON structure is missing."""


class BaseScraper(ABC):
    """Abstract base scraper contract for all site and API modules."""

    source_name: str

    @abstractmethod
    def collect(self, run_id: str | int) -> list[NormalizedPriceRecord]:
        """Fetch and parse normalized pricing records for this source."""
