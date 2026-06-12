"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { closeInvestment, listInvestments } from "../../lib/api";
import type { FinalVerdict, InvestmentsResponse, PaperPosition } from "../../lib/types";

const REFRESH_MS = 15_000;

export default function InvestmentsPage() {
  const [data, setData] = useState<InvestmentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [closingId, setClosingId] = useState<string | null>(null);
  const initialLoad = useRef(true);

  const load = useCallback(async () => {
    if (initialLoad.current) {
      setLoading(true);
    }
    try {
      setData(await listInvestments());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
      initialLoad.current = false;
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  const handleClose = async (id: string) => {
    setClosingId(id);
    try {
      await closeInvestment(id);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setClosingId(null);
    }
  };

  const wallet = data?.wallet;
  const positions = data?.positions ?? [];

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 pb-12 pt-8 md:px-6">
      <section className="mb-6 flex flex-wrap items-end justify-between gap-3 animate-riseIn">
        <div>
          <p className="font-display text-xs uppercase tracking-[0.28em] text-ink-soft">
            Paper Trading
          </p>
          <h1 className="mt-2 font-display text-3xl font-semibold leading-tight md:text-4xl">
            Investments
          </h1>
          <p className="mt-2 text-sm text-ink-soft">
            Mock portfolio · prices refresh every {REFRESH_MS / 1000}s
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-xl border border-border bg-white px-3 py-2 text-sm font-medium text-ink-soft transition hover:border-accent hover:text-ink"
        >
          Refresh
        </button>
      </section>

      {wallet ? (
        <section className="mb-4 grid grid-cols-2 gap-3 animate-riseIn md:grid-cols-4">
          <StatCard label="Total Value" value={formatCurrency(wallet.total_value)} emphasis />
          <StatCard
            label="Total P&L"
            value={`${signed(wallet.total_pnl)} (${signedPct(wallet.total_pnl_pct)})`}
            tone={wallet.total_pnl >= 0 ? "positive" : "negative"}
          />
          <StatCard label="Available Cash" value={formatCurrency(wallet.cash)} />
          <StatCard label="Holdings" value={formatCurrency(wallet.holdings_value)} />
          <StatCard label="Invested (open)" value={formatCurrency(wallet.invested)} />
          <StatCard
            label="Unrealized P&L"
            value={signed(wallet.unrealized_pnl)}
            tone={wallet.unrealized_pnl >= 0 ? "positive" : "negative"}
          />
          <StatCard
            label="Realized P&L"
            value={signed(wallet.realized_pnl)}
            tone={wallet.realized_pnl >= 0 ? "positive" : "negative"}
          />
          <StatCard label="Starting Cash" value={formatCurrency(wallet.starting_cash)} />
        </section>
      ) : null}

      <section className="panel animate-riseIn overflow-hidden p-0">
        {error ? (
          <p className="px-5 py-4 text-sm text-rose-700">{error}</p>
        ) : loading && !data ? (
          <p className="px-5 py-6 text-sm text-ink-soft">Loading portfolio…</p>
        ) : positions.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-ink-soft">No investments yet.</p>
            <Link href="/" className="mt-2 inline-block text-sm font-semibold text-accent underline">
              Run an analysis, then invest from the run page
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-[0.12em] text-ink-soft">
                  <th className="px-4 py-3 font-semibold">Stock</th>
                  <th className="px-4 py-3 font-semibold">Verdict</th>
                  <th className="px-4 py-3 text-right font-semibold">Qty</th>
                  <th className="px-4 py-3 text-right font-semibold">Entry</th>
                  <th className="px-4 py-3 text-right font-semibold">Current</th>
                  <th className="px-4 py-3 text-right font-semibold">Invested</th>
                  <th className="px-4 py-3 text-right font-semibold">Value</th>
                  <th className="px-4 py-3 text-right font-semibold">P&amp;L</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => (
                  <PositionRow
                    key={position.id}
                    position={position}
                    closing={closingId === position.id}
                    onClose={() => handleClose(position.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

function PositionRow({
  position,
  closing,
  onClose,
}: {
  position: PaperPosition;
  closing: boolean;
  onClose: () => void;
}) {
  const isOpen = position.status === "open";
  const pnlPositive = position.pnl >= 0;
  return (
    <tr className="border-b border-border/70 last:border-0">
      <td className="px-4 py-3">
        {position.run_id ? (
          <Link href={`/runs/${position.run_id}`} className="font-medium text-ink hover:text-accent">
            {position.ticker}
          </Link>
        ) : (
          <span className="font-medium text-ink">{position.ticker}</span>
        )}
      </td>
      <td className="px-4 py-3">
        {position.verdict ? (
          <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${verdictClass(position.verdict)}`}>
            {position.verdict === "no_recommendation" ? "NO REC" : position.verdict.toUpperCase()}
          </span>
        ) : (
          <span className="text-ink-soft">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-ink-soft">{position.quantity.toFixed(3)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{formatCurrency(position.entry_price)}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        {position.current_price !== null ? formatCurrency(position.current_price) : "—"}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-ink-soft">
        {formatCurrency(position.invested_amount)}
      </td>
      <td className="px-4 py-3 text-right tabular-nums">
        {position.current_value !== null ? formatCurrency(position.current_value) : "—"}
      </td>
      <td className={`px-4 py-3 text-right tabular-nums font-medium ${pnlPositive ? "text-emerald-700" : "text-rose-700"}`}>
        {signed(position.pnl)}
        <span className="ml-1 text-xs opacity-70">({signedPct(position.pnl_pct)})</span>
      </td>
      <td className="px-4 py-3">
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
            isOpen ? "border-accent/30 bg-orange-50 text-accent" : "border-border bg-white text-ink-soft"
          }`}
        >
          {position.status}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        {isOpen ? (
          <button
            type="button"
            onClick={onClose}
            disabled={closing}
            className="rounded-lg border border-rose-300 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 transition hover:bg-rose-100 disabled:opacity-60"
          >
            {closing ? "Selling…" : "Sell"}
          </button>
        ) : null}
      </td>
    </tr>
  );
}

function StatCard({
  label,
  value,
  tone,
  emphasis,
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative";
  emphasis?: boolean;
}) {
  const toneClass =
    tone === "positive" ? "text-emerald-700" : tone === "negative" ? "text-rose-700" : "text-ink";
  return (
    <div className="panel p-4">
      <p className="text-xs uppercase tracking-[0.1em] text-ink-soft">{label}</p>
      <p className={`mt-1 font-display ${emphasis ? "text-2xl" : "text-lg"} font-semibold ${toneClass}`}>
        {value}
      </p>
    </div>
  );
}

function verdictClass(verdict: FinalVerdict): string {
  if (verdict === "buy") {
    return "border-emerald-300 bg-emerald-50 text-emerald-800";
  }
  if (verdict === "sell") {
    return "border-rose-300 bg-rose-50 text-rose-800";
  }
  if (verdict === "hold") {
    return "border-sky-300 bg-sky-50 text-sky-800";
  }
  return "border-amber-300 bg-amber-50 text-amber-800";
}

function formatCurrency(value: number): string {
  return `₹${value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function signed(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${formatCurrency(Math.abs(value))}`;
}

function signedPct(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(2)}%`;
}
