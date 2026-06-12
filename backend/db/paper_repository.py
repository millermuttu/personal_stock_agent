from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.models import PaperPositionORM
from backend.models.schemas import PositionStatus, utc_now


@dataclass
class StoredPosition:
    id: str
    run_id: str | None
    ticker: str
    verdict: str | None
    status: str
    entry_price: float
    quantity: float
    invested_amount: float
    opened_at: datetime
    closed_at: datetime | None = None
    close_price: float | None = None
    realized_pnl: float | None = None


class PositionNotFoundError(Exception):
    pass


def _new_position_id() -> str:
    return f"pos_{uuid.uuid4().hex[:12]}"


class PaperTradingRepository(Protocol):
    async def create_position(
        self,
        *,
        run_id: str | None,
        ticker: str,
        verdict: str | None,
        entry_price: float,
        quantity: float,
        invested_amount: float,
    ) -> StoredPosition: ...

    async def list_positions(self) -> list[StoredPosition]: ...

    async def get_position(self, position_id: str) -> StoredPosition: ...

    async def close_position(
        self,
        position_id: str,
        *,
        close_price: float,
        realized_pnl: float,
    ) -> StoredPosition: ...


class InMemoryPaperRepository:
    def __init__(self) -> None:
        self._positions: dict[str, StoredPosition] = {}
        self._lock = asyncio.Lock()

    async def create_position(
        self,
        *,
        run_id: str | None,
        ticker: str,
        verdict: str | None,
        entry_price: float,
        quantity: float,
        invested_amount: float,
    ) -> StoredPosition:
        position = StoredPosition(
            id=_new_position_id(),
            run_id=run_id,
            ticker=ticker,
            verdict=verdict,
            status=PositionStatus.OPEN.value,
            entry_price=entry_price,
            quantity=quantity,
            invested_amount=invested_amount,
            opened_at=utc_now(),
        )
        async with self._lock:
            self._positions[position.id] = position
        return position

    async def list_positions(self) -> list[StoredPosition]:
        async with self._lock:
            return sorted(
                self._positions.values(),
                key=lambda position: position.opened_at,
                reverse=True,
            )

    async def get_position(self, position_id: str) -> StoredPosition:
        async with self._lock:
            position = self._positions.get(position_id)
            if position is None:
                raise PositionNotFoundError(position_id)
            return position

    async def close_position(
        self,
        position_id: str,
        *,
        close_price: float,
        realized_pnl: float,
    ) -> StoredPosition:
        async with self._lock:
            position = self._positions.get(position_id)
            if position is None:
                raise PositionNotFoundError(position_id)
            position.status = PositionStatus.CLOSED.value
            position.close_price = close_price
            position.realized_pnl = realized_pnl
            position.closed_at = utc_now()
            return position


class PostgresPaperRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_position(
        self,
        *,
        run_id: str | None,
        ticker: str,
        verdict: str | None,
        entry_price: float,
        quantity: float,
        invested_amount: float,
    ) -> StoredPosition:
        row = PaperPositionORM(
            id=_new_position_id(),
            run_id=run_id,
            ticker=ticker,
            verdict=verdict,
            status=PositionStatus.OPEN.value,
            entry_price=entry_price,
            quantity=quantity,
            invested_amount=invested_amount,
            opened_at=utc_now(),
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
        return await self.get_position(row.id)

    async def list_positions(self) -> list[StoredPosition]:
        async with self._session_factory() as session:
            stmt = select(PaperPositionORM).order_by(PaperPositionORM.opened_at.desc())
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_record(row) for row in rows]

    async def get_position(self, position_id: str) -> StoredPosition:
        async with self._session_factory() as session:
            row = await session.get(PaperPositionORM, position_id)
            if row is None:
                raise PositionNotFoundError(position_id)
            return self._to_record(row)

    async def close_position(
        self,
        position_id: str,
        *,
        close_price: float,
        realized_pnl: float,
    ) -> StoredPosition:
        async with self._session_factory() as session:
            row = await session.get(PaperPositionORM, position_id)
            if row is None:
                raise PositionNotFoundError(position_id)
            row.status = PositionStatus.CLOSED.value
            row.close_price = close_price
            row.realized_pnl = realized_pnl
            row.closed_at = utc_now()
            await session.commit()
            return self._to_record(row)

    @staticmethod
    def _to_record(row: PaperPositionORM) -> StoredPosition:
        return StoredPosition(
            id=row.id,
            run_id=row.run_id,
            ticker=row.ticker,
            verdict=row.verdict,
            status=row.status,
            entry_price=row.entry_price,
            quantity=row.quantity,
            invested_amount=row.invested_amount,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            close_price=row.close_price,
            realized_pnl=row.realized_pnl,
        )
