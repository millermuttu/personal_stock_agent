from __future__ import annotations

import asyncio
from typing import Protocol

from backend.models.schemas import INDIAN_EXCHANGE_SUFFIXES, StockSearchResult


class SymbolSearchProvider(Protocol):
    async def search(self, query: str, *, limit: int = 8) -> list[StockSearchResult]:
        ...


class YahooSymbolSearchProvider:
    """Resolves Indian (NSE/BSE) ticker suggestions from Yahoo's live search.

    Only symbols listed on Indian exchanges (``.NS`` / ``.BO``) are returned.
    Failures degrade to an empty suggestion list so the UI stays responsive;
    the analysis form accepts any ticker regardless of suggestions.
    """

    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def search(self, query: str, *, limit: int = 8) -> list[StockSearchResult]:
        normalized = query.strip()
        if not normalized:
            return []
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._search_sync, normalized, limit),
                timeout=self._timeout_seconds,
            )
        except Exception:  # pylint: disable=broad-except
            return []

    @staticmethod
    def _search_sync(query: str, limit: int) -> list[StockSearchResult]:
        import yfinance as yf

        quotes = yf.Search(query, max_results=limit).quotes or []
        results: list[StockSearchResult] = []
        seen: set[str] = set()
        for quote in quotes:
            if not isinstance(quote, dict):
                continue
            quote_type = str(quote.get("quoteType", "")).upper()
            if quote_type and quote_type != "EQUITY":
                continue
            symbol = quote.get("symbol")
            if not isinstance(symbol, str) or not symbol or symbol in seen:
                continue
            if not symbol.upper().endswith(INDIAN_EXCHANGE_SUFFIXES):
                continue
            seen.add(symbol)
            name = (
                quote.get("shortname")
                or quote.get("longname")
                or quote.get("shortName")
                or symbol
            )
            sector = quote.get("sector") or quote.get("exchDisp") or quote.get("exchange") or ""
            results.append(
                StockSearchResult(ticker=symbol, name=str(name), sector=str(sector))
            )
            if len(results) >= limit:
                break
        return results
