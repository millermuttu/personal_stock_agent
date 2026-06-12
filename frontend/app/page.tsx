"use client";

import { useRouter } from "next/navigation";
import {
  FormEvent,
  KeyboardEvent,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
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
  const [isSearching, setIsSearching] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const deferredTicker = useDeferredValue(tickerInput);
  const comboboxRef = useRef<HTMLDivElement>(null);

  // Close the suggestion dropdown on any click outside the combobox.
  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (comboboxRef.current && !comboboxRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

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
          setActiveIndex(-1);
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
      router.push(`/runs/${created.run_id}`);
    } catch (error) {
      setSubmitError((error as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectSuggestion = (ticker: string) => {
    setTickerInput(ticker);
    setIsOpen(false);
    setActiveIndex(-1);
  };

  const handleTickerKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen || suggestions.length === 0) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? suggestions.length - 1 : index - 1));
    } else if (event.key === "Enter") {
      if (activeIndex >= 0 && suggestions[activeIndex]) {
        // Choose the highlighted suggestion instead of submitting the form.
        event.preventDefault();
        selectSuggestion(suggestions[activeIndex].ticker);
      }
    } else if (event.key === "Escape") {
      setIsOpen(false);
      setActiveIndex(-1);
    }
  };

  const selectedTimeframe = TIMEFRAMES.find((item) => item.value === timeframe);
  const showDropdown = isOpen && tickerInput.trim().length > 0;

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

      <section className="max-w-xl">
        <div className="panel animate-riseIn p-5">
          <h2 className="font-display text-lg font-semibold">Run Form</h2>
          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <div ref={comboboxRef} className="relative">
              <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-ink-soft">
                Ticker
              </label>
              <input
                value={tickerInput}
                onChange={(event) => {
                  setTickerInput(event.target.value);
                  setIsOpen(true);
                  setActiveIndex(-1);
                }}
                onFocus={() => setIsOpen(true)}
                onKeyDown={handleTickerKeyDown}
                placeholder="RELIANCE"
                role="combobox"
                aria-expanded={showDropdown}
                aria-autocomplete="list"
                aria-controls="ticker-suggestions"
                autoComplete="off"
                className="w-full rounded-xl border border-border bg-white px-3 py-2 font-display text-lg uppercase outline-none transition focus:border-accent"
              />
              {showDropdown ? (
                <ul
                  id="ticker-suggestions"
                  role="listbox"
                  className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-auto rounded-xl border border-border bg-white py-1 shadow-panel"
                >
                  {isSearching && suggestions.length === 0 ? (
                    <li className="px-3 py-2 text-sm text-ink-soft">Searching…</li>
                  ) : null}
                  {!isSearching && suggestions.length === 0 && !searchError ? (
                    <li className="px-3 py-2 text-sm text-ink-soft">No matches</li>
                  ) : null}
                  {searchError ? (
                    <li className="px-3 py-2 text-sm text-red-600">{searchError}</li>
                  ) : null}
                  {suggestions.map((item, index) => (
                    <li key={item.ticker} role="option" aria-selected={index === activeIndex}>
                      <button
                        type="button"
                        onMouseEnter={() => setActiveIndex(index)}
                        onClick={() => selectSuggestion(item.ticker)}
                        className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition ${
                          index === activeIndex ? "bg-orange-50 text-ink" : "text-ink hover:bg-canvas"
                        }`}
                      >
                        <span className="font-mono font-semibold">{item.ticker}</span>
                        <span className="min-w-0 flex-1 truncate text-right text-ink-soft">
                          {item.name}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
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
              {selectedTimeframe?.detail ? (
                <p className="mt-1 text-xs text-ink-soft">{selectedTimeframe.detail}</p>
              ) : null}
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? "Creating Run..." : "Create Run"}
            </button>
          </form>

          {submitError ? <p className="mt-3 text-sm text-red-600">{submitError}</p> : null}
        </div>
      </section>
    </main>
  );
}
