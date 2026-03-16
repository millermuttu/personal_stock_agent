import sys
from types import SimpleNamespace

from backend.services.providers.news_sentiment import YahooNewsSentimentProvider


def test_yahoo_news_extracts_nested_content_titles(monkeypatch):
    news_payload = [
        {"id": "1", "content": {"title": "Apple expands services bundle"}},
        {"id": "2", "content": {"title": "Apple expands services bundle"}},
        {"id": "3", "title": "Analysts debate Apple valuation"},
    ]

    class FakeTicker:
        def __init__(self, ticker: str):
            self.ticker = ticker
            self.news = news_payload

    fake_yfinance = SimpleNamespace(Ticker=lambda ticker: FakeTicker(ticker))
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    headlines = YahooNewsSentimentProvider._fetch_sync("AAPL", 8)
    assert headlines == [
        "Apple expands services bundle",
        "Analysts debate Apple valuation",
    ]
