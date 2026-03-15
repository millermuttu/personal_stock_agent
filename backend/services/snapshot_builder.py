from __future__ import annotations

import hashlib
import random

from backend.models.schemas import DataSnapshot, ProviderManifest, SnapshotFeatures, Timeframe, utc_now


class SnapshotBuilder:
    """Builds deterministic mock snapshots for local development."""

    async def build(self, ticker: str, timeframe: Timeframe) -> DataSnapshot:
        as_of = utc_now()
        seed = self._seed_from_inputs(ticker=ticker, timeframe=timeframe.value)
        rng = random.Random(seed)

        base_price = 90 + (seed % 120)
        price_history = [
            round(base_price + (index * 0.45) + rng.uniform(-2.5, 2.5), 2)
            for index in range(30)
        ]

        technical_indicators = {
            "rsi": round(25 + rng.uniform(0, 55), 2),
            "macd_signal": round(rng.uniform(-2.0, 2.0), 2),
            "ma20": round(sum(price_history[-20:]) / 20, 2),
            "ma50": round(sum(price_history) / len(price_history), 2),
            "ma200": round(base_price + rng.uniform(-10, 10), 2),
            "bollinger_position": round(rng.uniform(0.0, 1.0), 2),
            "volatility": round(rng.uniform(0.15, 0.65), 2),
        }

        fundamental_metrics = {
            "revenue_growth": round(rng.uniform(-0.08, 0.35), 3),
            "profit_margin": round(rng.uniform(0.02, 0.4), 3),
            "de_ratio": round(rng.uniform(0.05, 2.2), 2),
            "roe": round(rng.uniform(0.01, 0.42), 3),
            "pe_ratio": round(rng.uniform(8, 52), 2),
            "fcf": round(rng.uniform(-1.5, 12.0), 2),
        }

        risk_metrics = {
            "volatility": technical_indicators["volatility"],
            "beta": round(rng.uniform(0.6, 2.1), 2),
            "max_drawdown": round(rng.uniform(-0.72, -0.1), 3),
        }

        news_items = self._mock_news(ticker=ticker, rng=rng)
        quality_flags: list[str] = []
        if len(news_items) < 2:
            quality_flags.append("low_news_coverage")

        snapshot_id = f"snap_{hashlib.sha1(f'{ticker}:{as_of.isoformat()}'.encode('utf-8')).hexdigest()[:12]}"
        return DataSnapshot(
            snapshot_id=snapshot_id,
            target_id=ticker,
            as_of=as_of,
            providers=[
                ProviderManifest(name="mock_market_data_provider", fetched_at=as_of),
                ProviderManifest(name="mock_fundamentals_provider", fetched_at=as_of),
                ProviderManifest(name="mock_news_provider", fetched_at=as_of),
            ],
            data_quality_flags=quality_flags,
            features=SnapshotFeatures(
                price_history=price_history,
                technical_indicators=technical_indicators,
                fundamental_metrics=fundamental_metrics,
                news_items=news_items,
                risk_metrics=risk_metrics,
            ),
        )

    @staticmethod
    def _seed_from_inputs(*, ticker: str, timeframe: str) -> int:
        digest = hashlib.sha256(f"{ticker}:{timeframe}".encode("utf-8")).hexdigest()
        return int(digest[:10], 16)

    @staticmethod
    def _mock_news(*, ticker: str, rng: random.Random) -> list[str]:
        pool = [
            f"{ticker} expands cloud partnership with enterprise customer",
            f"{ticker} faces analyst debate on valuation after earnings",
            f"{ticker} announces product roadmap update for next quarter",
            f"Macro data drives sector-wide volatility impacting {ticker}",
            f"{ticker} reports stronger-than-expected operating margin",
        ]
        rng.shuffle(pool)
        count = rng.randint(1, 5)
        return pool[:count]

