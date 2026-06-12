import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

from backend.db.paper_repository import InMemoryPaperRepository
from backend.db.repositories import InMemoryRunRepository
from backend.models.schemas import OpenInvestmentRequest
from backend.services.paper_trading_service import (
    STARTING_CASH,
    InsufficientFundsError,
    PaperTradingService,
)


class StubPriceProvider:
    """Returns a configurable per-ticker price; mutate `prices` to simulate moves."""

    def __init__(self, prices: dict[str, float]):
        self.prices = prices

    async def fetch_current_price(self, *, ticker: str) -> float:
        return self.prices[ticker]


def _service(prices: dict[str, float]) -> PaperTradingService:
    return PaperTradingService(
        repository=InMemoryPaperRepository(),
        run_repository=InMemoryRunRepository(),
        market_data_provider=StubPriceProvider(prices),
    )


def test_open_then_price_rises_shows_unrealized_profit():
    provider = StubPriceProvider({"TCS.NS": 100.0})
    service = PaperTradingService(
        repository=InMemoryPaperRepository(),
        run_repository=InMemoryRunRepository(),
        market_data_provider=provider,
    )

    async def run():
        pos = await service.open_investment(
            OpenInvestmentRequest(ticker="TCS", amount=10_000.0)
        )
        assert pos.entry_price == 100.0
        assert pos.quantity == pytest.approx(100.0)

        # Price climbs 20% -> +2,000 unrealized.
        provider.prices["TCS.NS"] = 120.0
        listing = await service.list_investments()
        assert len(listing.positions) == 1
        p = listing.positions[0]
        assert p.current_price == 120.0
        assert p.current_value == pytest.approx(12_000.0)
        assert p.pnl == pytest.approx(2_000.0)
        assert p.pnl_pct == pytest.approx(20.0)

        w = listing.wallet
        assert w.cash == pytest.approx(STARTING_CASH - 10_000.0)
        assert w.holdings_value == pytest.approx(12_000.0)
        assert w.unrealized_pnl == pytest.approx(2_000.0)
        assert w.total_value == pytest.approx(STARTING_CASH + 2_000.0)

    asyncio.run(run())


def test_close_realizes_pnl_and_returns_cash():
    provider = StubPriceProvider({"INFY.NS": 50.0})
    service = PaperTradingService(
        repository=InMemoryPaperRepository(),
        run_repository=InMemoryRunRepository(),
        market_data_provider=provider,
    )

    async def run():
        pos = await service.open_investment(
            OpenInvestmentRequest(ticker="INFY", amount=5_000.0)
        )
        provider.prices["INFY.NS"] = 60.0  # +20%
        closed = await service.close_investment(pos.id)
        assert closed.status.value == "closed"
        assert closed.close_price == 60.0
        assert closed.pnl == pytest.approx(1_000.0)

        listing = await service.list_investments()
        w = listing.wallet
        # Cash returns to starting + realized gain; nothing held.
        assert w.holdings_value == pytest.approx(0.0)
        assert w.realized_pnl == pytest.approx(1_000.0)
        assert w.cash == pytest.approx(STARTING_CASH + 1_000.0)
        assert w.total_value == pytest.approx(STARTING_CASH + 1_000.0)

    asyncio.run(run())


def test_cannot_invest_more_than_available_cash():
    service = _service({"RELIANCE.NS": 100.0})

    async def run():
        with pytest.raises(InsufficientFundsError):
            await service.open_investment(
                OpenInvestmentRequest(ticker="RELIANCE", amount=STARTING_CASH + 1.0)
            )

    asyncio.run(run())
