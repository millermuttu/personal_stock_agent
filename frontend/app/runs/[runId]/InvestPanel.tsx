"use client";

import Link from "next/link";
import { useState } from "react";
import { openInvestment } from "../../../lib/api";
import type { PaperPosition } from "../../../lib/types";

export function InvestPanel({
  ticker,
  runId,
}: {
  ticker: string;
  runId: string;
}) {
  const [amount, setAmount] = useState("10000");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PaperPosition | null>(null);

  const handleInvest = async () => {
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError("Enter a valid amount greater than 0.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const position = await openInvestment({ ticker, amount: parsed, run_id: runId });
      setResult(position);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="panel animate-riseIn p-5 [animation-delay:60ms]">
      <h3 className="font-display text-lg font-semibold">Paper Trade</h3>
      <p className="mt-1 text-sm text-ink-soft">
        Invest mock money in <span className="font-mono">{ticker}</span> at the live price and track
        it in Investments.
      </p>

      {result ? (
        <div className="mt-4 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <p className="font-semibold">Position opened</p>
          <p className="mt-1">
            Bought {result.quantity.toFixed(3)} @ {formatCurrency(result.entry_price)} for{" "}
            {formatCurrency(result.invested_amount)}.
          </p>
          <div className="mt-3 flex gap-2">
            <Link
              href="/investments"
              className="rounded-lg bg-accent-2 px-3 py-1.5 text-xs font-semibold text-white transition hover:brightness-95"
            >
              View Investments
            </Link>
            <button
              type="button"
              onClick={() => setResult(null)}
              className="rounded-lg border border-border bg-white px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:text-ink"
            >
              Invest again
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="mt-4">
            <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-ink-soft">
              Amount (₹)
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="number"
                min={1}
                step={1000}
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className="w-40 rounded-xl border border-border bg-white px-3 py-2 font-display text-lg outline-none transition focus:border-accent"
              />
              <div className="flex gap-1">
                {[10000, 50000, 100000].map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setAmount(String(preset))}
                    className="chip transition hover:border-accent hover:text-ink"
                  >
                    ₹{preset.toLocaleString("en-IN")}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleInvest()}
            disabled={submitting}
            className="mt-4 w-full rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {submitting ? "Placing order…" : "Invest (Buy)"}
          </button>
          {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        </>
      )}
    </div>
  );
}

function formatCurrency(value: number): string {
  return `₹${value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
