"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useDeferredValue, useEffect, useState } from "react";
import { createAnalysis, searchStocks } from "../lib/api";
import type { StockSearchResult, Timeframe } from "../lib/types";

const TIMEFRAMES: Array<{ value: Timeframe; label: string; detail: string }> = [
  { value: "short", label: "Short", detail: "Tactical setup with high sensitivity to volatility." },
  { value: "medium", label: "Medium", detail: "Balanced horizon across trend and valuation signals." },
  { value: "long", label: "Long", detail: "Long-term conviction with risk-first constraints." },
];

export default function HomePage() {
  const router = useRouter();
  const [tickerInput, setTickerInput] = useState("RELIANCE");
  const [timeframe, setTimeframe] = useState<Timeframe>("short");
  const [suggestions, setSuggestions] = useState<StockSearchResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [recentRunId, setRecentRunId] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const deferredTicker = useDeferredValue(tickerInput);

  useEffect(() => {
    const normalized = deferredTicker.trim().toUpperCase();
    if (!normalized) {
      setSuggestions([]);
      return;
    }

    let cancelled = false;
    const timerId = window.setTimeout(async () => {
      setIsSearching(true);
      setSearchError(null);
      try {
        const results = await searchStocks(normalized);
        if (!cancelled) {
          setSuggestions(results.slice(0, 6));
        }
      } catch (error) {
        if (!cancelled) {
          setSearchError((error as Error).message);
          setSuggestions([]);
        }
      } finally {
        if (!cancelled) {
          setIsSearching(false);
        }
      }
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(timerId);
    };
  }, [deferredTicker]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedTicker = tickerInput.trim().toUpperCase();
    if (!normalizedTicker) {
      setSubmitError("Ticker is required.");
      return;
    }

    try {
      setIsSubmitting(true);
      setSubmitError(null);
      const created = await createAnalysis({
        ticker: normalizedTicker,
        timeframe,
      });
      setRecentRunId(created.run_id);
      router.push(`/runs/${created.run_id}`);
    } catch (error) {
      setSubmitError((error as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectedTimeframe = TIMEFRAMES.find((item) => item.value === timeframe);

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 pb-12 pt-8 md:px-6">
      <section className="mb-6 animate-riseIn">
        <p className="font-display text-xs uppercase tracking-[0.28em] text-ink-soft">Stock Agent</p>
        <h1 className="mt-2 font-display text-4xl font-semibold leading-tight md:text-5xl">
          Start New Analysis
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-ink-soft md:text-base">
          Indian market (NSE/BSE) only. Submit an NSE ticker + timeframe to launch a run, then
          inspect orchestration progress on the run details page. A bare symbol like{" "}
          <span className="font-mono">RELIANCE</span> routes to NSE; add{" "}
          <span className="font-mono">.BO</span> for BSE.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-[1.2fr_1fr]">
        <div className="panel animate-riseIn p-5">
          <h2 className="font-display text-lg font-semibold">Run Form</h2>
          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-ink-soft">
                Ticker
              </label>
              <input
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                placeholder="RELIANCE"
                className="w-full rounded-xl border border-border bg-white px-3 py-2 font-display text-lg uppercase outline-none transition focus:border-accent"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-ink-soft">
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(event) => setTimeframe(event.target.value as Timeframe)}
                className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm outline-none transition focus:border-accent"
              >
                {TIMEFRAMES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? "Creating Run..." : "Create Run"}
            </button>
          </form>

          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-soft">
              Ticker Suggestions
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {isSearching ? <span className="chip">Loading...</span> : null}
              {!isSearching && suggestions.length === 0 ? (
                <span className="chip">No matches</span>
              ) : null}
              {suggestions.map((item) => (
                <button
                  key={item.ticker}
                  type="button"
                  onClick={() => setTickerInput(item.ticker)}
                  className="chip transition hover:border-accent hover:text-ink"
                >
                  {item.ticker} · {item.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="panel animate-riseIn p-5 [animation-delay:120ms]">
          <h2 className="font-display text-lg font-semibold">Run Handoff</h2>
          <p className="mt-2 text-sm text-ink-soft">
            After submitting, you’ll be redirected to a dedicated run page:
          </p>
          <div className="mt-3 rounded-xl border border-border bg-white px-3 py-2 font-mono text-xs text-ink-soft">
            /runs/&lt;run_id&gt;
          </div>
          <p className="mt-3 text-sm text-ink-soft">
            {selectedTimeframe?.detail}
          </p>

          {recentRunId ? (
            <div className="mt-4 rounded-xl border border-accent/30 bg-orange-50 px-3 py-2 text-sm">
              Recent run:{" "}
              <Link className="font-semibold text-accent underline" href={`/runs/${recentRunId}`}>
                {recentRunId}
              </Link>
            </div>
          ) : null}

          {searchError ? <p className="mt-4 text-sm text-red-600">{searchError}</p> : null}
          {submitError ? <p className="mt-2 text-sm text-red-600">{submitError}</p> : null}
        </div>
      </section>
    </main>
  );
}
