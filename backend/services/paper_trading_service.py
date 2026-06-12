from __future__ import annotations

import asyncio

from backend.db.paper_repository import (
    PaperTradingRepository,
    PositionNotFoundError,
    StoredPosition,
)
from backend.db.repositories import RunNotFoundError, RunRepository
from backend.models.schemas import (
    FinalVerdict,
    InvestmentsResponse,
    OpenInvestmentRequest,
    PaperPosition,
    PositionStatus,
    WalletSummary,
)
from backend.services.providers.market_data import (
    MarketDataProvider,
    MarketDataProviderError,
    YahooFinanceMarketDataProvider,
)

# Virtual starting balance for the paper-trading wallet (₹10,00,000).
STARTING_CASH = 1_000_000.0


class InsufficientFundsError(Exception):
    pass


class PaperTradingError(Exception):
    pass


class PaperTradingService:
    def __init__(
        self,
        repository: PaperTradingRepository,
        run_repository: RunRepository,
        market_data_provider: MarketDataProvider | None = None,
    ) -> None:
        self._repository = repository
        self._run_repository = run_repository
        self._market_data_provider = market_data_provider or YahooFinanceMarketDataProvider()

    async def open_investment(self, request: OpenInvestmentRequest) -> PaperPosition:
        existing = await self._repository.list_positions()
        wallet = self._wallet_from_stored(existing, prices={})
        if request.amount > wallet.cash + 1e-6:
            raise InsufficientFundsError(
                f"amount {request.amount:.2f} exceeds available cash {wallet.cash:.2f}"
            )

        try:
            entry_price = await self._market_data_provider.fetch_current_price(ticker=request.ticker)
        except MarketDataProviderError as exc:
            raise PaperTradingError(str(exc)) from exc
        if entry_price <= 0:
            raise PaperTradingError(f"invalid entry price for {request.ticker}")

        verdict = await self._verdict_for_run(request.run_id)
        quantity = request.amount / entry_price
        stored = await self._repository.create_position(
            run_id=request.run_id,
            ticker=request.ticker,
            verdict=verdict.value if verdict else None,
            entry_price=round(entry_price, 4),
            quantity=quantity,
            invested_amount=request.amount,
        )
        return self._to_position(stored, current_price=entry_price)

    async def list_investments(self) -> InvestmentsResponse:
        positions = await self._repository.list_positions()
        prices = await self._current_prices(
            {p.ticker for p in positions if p.status == PositionStatus.OPEN.value}
        )
        wallet = self._wallet_from_stored(positions, prices)
        return InvestmentsResponse(
            wallet=wallet,
            positions=[self._to_position(p, current_price=prices.get(p.ticker)) for p in positions],
        )

    async def close_investment(self, position_id: str) -> PaperPosition:
        try:
            stored = await self._repository.get_position(position_id)
        except PositionNotFoundError as exc:
            raise PaperTradingError(f"position not found: {position_id}") from exc
        if stored.status == PositionStatus.CLOSED.value:
            raise PaperTradingError("position is already closed")

        try:
            close_price = await self._market_data_provider.fetch_current_price(ticker=stored.ticker)
        except MarketDataProviderError as exc:
            raise PaperTradingError(str(exc)) from exc

        realized_pnl = (close_price - stored.entry_price) * stored.quantity
        closed = await self._repository.close_position(
            position_id,
            close_price=round(close_price, 4),
            realized_pnl=round(realized_pnl, 4),
        )
        return self._to_position(closed, current_price=close_price)

    # -- internals -------------------------------------------------------------

    async def _verdict_for_run(self, run_id: str | None) -> FinalVerdict | None:
        if not run_id:
            return None
        try:
            run = await self._run_repository.get_run(run_id)
        except RunNotFoundError:
            return None
        if run.final_report is None:
            return None
        return run.final_report.final_verdict

    async def _current_prices(self, tickers: set[str]) -> dict[str, float]:
        async def fetch(ticker: str) -> tuple[str, float | None]:
            try:
                price = await self._market_data_provider.fetch_current_price(ticker=ticker)
                return ticker, price
            except Exception:  # pylint: disable=broad-except
                return ticker, None

        results = await asyncio.gather(*(fetch(ticker) for ticker in tickers))
        return {ticker: price for ticker, price in results if price is not None}

    def _to_position(self, stored: StoredPosition, *, current_price: float | None) -> PaperPosition:
        is_open = stored.status == PositionStatus.OPEN.value
        if is_open:
            price = current_price
            current_value = price * stored.quantity if price is not None else None
            if current_value is not None:
                pnl = current_value - stored.invested_amount
            else:
                pnl = 0.0
        else:
            price = stored.close_price
            current_value = (
                stored.close_price * stored.quantity if stored.close_price is not None else None
            )
            pnl = stored.realized_pnl if stored.realized_pnl is not None else 0.0

        pnl_pct = (pnl / stored.invested_amount * 100.0) if stored.invested_amount else 0.0
        return PaperPosition(
            id=stored.id,
            run_id=stored.run_id,
            ticker=stored.ticker,
            verdict=_safe_verdict(stored.verdict),
            status=PositionStatus(stored.status),
            entry_price=stored.entry_price,
            quantity=stored.quantity,
            invested_amount=stored.invested_amount,
            opened_at=stored.opened_at,
            closed_at=stored.closed_at,
            close_price=stored.close_price,
            current_price=round(price, 4) if price is not None else None,
            current_value=round(current_value, 2) if current_value is not None else None,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        )

    def _wallet_from_stored(
        self,
        positions: list[StoredPosition],
        prices: dict[str, float],
    ) -> WalletSummary:
        invested_open = 0.0
        holdings_value = 0.0
        realized_pnl = 0.0
        for position in positions:
            if position.status == PositionStatus.OPEN.value:
                invested_open += position.invested_amount
                price = prices.get(position.ticker)
                # Fall back to entry price when a live quote is unavailable.
                effective = price if price is not None else position.entry_price
                holdings_value += effective * position.quantity
            else:
                realized_pnl += position.realized_pnl or 0.0

        cash = STARTING_CASH - invested_open + realized_pnl
        unrealized_pnl = holdings_value - invested_open
        total_value = cash + holdings_value
        total_pnl = total_value - STARTING_CASH
        total_pnl_pct = (total_pnl / STARTING_CASH * 100.0) if STARTING_CASH else 0.0
        return WalletSummary(
            starting_cash=STARTING_CASH,
            cash=round(cash, 2),
            invested=round(invested_open, 2),
            holdings_value=round(holdings_value, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            realized_pnl=round(realized_pnl, 2),
            total_value=round(total_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
        )


def _safe_verdict(value: str | None) -> FinalVerdict | None:
    if value is None:
        return None
    try:
        return FinalVerdict(value)
    except ValueError:
        return None
