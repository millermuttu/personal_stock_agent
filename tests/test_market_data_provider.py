import sys
from types import SimpleNamespace

import pandas as pd

from backend.services.providers.market_data import YahooFinanceMarketDataProvider


def test_yahoo_extract_closes_handles_dataframe_shape(monkeypatch):
    history = pd.DataFrame(
        {
            ("Close", "AAPL"): [180.0, 181.5, None, 182.25],
            ("Open", "AAPL"): [179.5, 180.2, 181.0, 181.7],
        }
    )

    fake_yfinance = SimpleNamespace(download=lambda **_: history)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    closes = YahooFinanceMarketDataProvider._fetch_sync(
        ticker="AAPL",
        period="3mo",
        timeout_seconds=5.0,
    )
    assert closes == [180.0, 181.5, 182.25]
