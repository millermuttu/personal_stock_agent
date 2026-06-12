import sys
from types import SimpleNamespace

from backend.services.providers.news_sentiment import YahooNewsSentimentProvider


def test_yahoo_news_extracts_nested_content_titles(monkeypatch):
    news_payload = [
        {
            "id": "1",
            "content": {
                "title": "Apple expands services bundle",
                "provider": {"displayName": "Reuters"},
                "clickThroughUrl": {"url": "https://example.com/apple-services"},
                "pubDate": "2026-06-10T12:00:00Z",
            },
        },
        {"id": "2", "content": {"title": "Apple expands services bundle"}},
        {
            "id": "3",
            "title": "Analysts debate Apple valuation",
            "link": "https://example.com/apple-valuation",
            "publisher": "Bloomberg",
        },
    ]

    class FakeTicker:
        def __init__(self, ticker: str):
            self.ticker = ticker
            self.news = news_payload

    fake_yfinance = SimpleNamespace(Ticker=lambda ticker: FakeTicker(ticker))
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    articles = YahooNewsSentimentProvider._fetch_sync("AAPL", 8)

    assert [article.title for article in articles] == [
        "Apple expands services bundle",
        "Analysts debate Apple valuation",
    ]
    assert articles[0].url == "https://example.com/apple-services"
    assert articles[0].source == "Reuters"
    assert articles[0].published_at == "2026-06-10T12:00:00Z"
    assert articles[1].url == "https://example.com/apple-valuation"
    assert articles[1].source == "Bloomberg"
