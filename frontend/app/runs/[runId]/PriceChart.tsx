"use client";

import type { IChartApi, UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import { getCandles } from "../../../lib/api";
import type { CandleBar, PriceRange } from "../../../lib/types";

type ChartType = "candle" | "line";

const RANGES: PriceRange[] = ["1D", "5D", "1W", "1M", "3M", "6M"];

const UP_COLOR = "#136f63";
const DOWN_COLOR = "#c2485f";
const LINE_COLOR = "#eb6f1f";

export function PriceChart({ ticker }: { ticker: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [range, setRange] = useState<PriceRange>("1M");
  const [chartType, setChartType] = useState<ChartType>("candle");
  const [bars, setBars] = useState<CandleBar[]>([]);
  const [interval, setIntervalLabel] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCandles(ticker, range)
      .then((res) => {
        if (cancelled) {
          return;
        }
        setBars(dedupeSorted(res.bars));
        setIntervalLabel(res.interval);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError((err as Error).message);
          setBars([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ticker, range]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || bars.length === 0) {
      return;
    }
    let disposed = false;
    let chart: IChartApi | null = null;
    let resizeObserver: ResizeObserver | null = null;

    void (async () => {
      const lw = await import("lightweight-charts");
      if (disposed || !el) {
        return;
      }
      chart = lw.createChart(el, {
        width: el.clientWidth,
        height: 320,
        layout: {
          background: { type: lw.ColorType.Solid, color: "#ffffff" },
          textColor: "#4a5c76",
          fontFamily: "IBM Plex Sans, Manrope, sans-serif",
        },
        grid: {
          vertLines: { color: "rgba(216, 225, 238, 0.6)" },
          horzLines: { color: "rgba(216, 225, 238, 0.6)" },
        },
        rightPriceScale: { borderColor: "#d8e1ee" },
        timeScale: { borderColor: "#d8e1ee", timeVisible: true, secondsVisible: false },
        crosshair: { mode: lw.CrosshairMode.Normal },
        autoSize: false,
      });

      if (chartType === "candle") {
        const series = chart.addCandlestickSeries({
          upColor: UP_COLOR,
          downColor: DOWN_COLOR,
          borderUpColor: UP_COLOR,
          borderDownColor: DOWN_COLOR,
          wickUpColor: UP_COLOR,
          wickDownColor: DOWN_COLOR,
        });
        series.setData(
          bars.map((bar) => ({
            time: bar.time as UTCTimestamp,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          })),
        );
      } else {
        const trendUp = bars[bars.length - 1].close >= bars[0].close;
        const series = chart.addLineSeries({
          color: trendUp ? UP_COLOR : DOWN_COLOR,
          lineWidth: 2,
        });
        series.setData(
          bars.map((bar) => ({ time: bar.time as UTCTimestamp, value: bar.close })),
        );
      }
      chart.timeScale().fitContent();

      resizeObserver = new ResizeObserver(() => {
        if (chart && el) {
          chart.applyOptions({ width: el.clientWidth });
        }
      });
      resizeObserver.observe(el);
    })();

    return () => {
      disposed = true;
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (chart) {
        chart.remove();
      }
    };
  }, [bars, chartType]);

  const summary = summarize(bars);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1">
          {RANGES.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setRange(value)}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                range === value
                  ? "bg-accent text-white"
                  : "border border-border bg-white text-ink-soft hover:border-accent hover:text-ink"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          <ToggleButton active={chartType === "candle"} onClick={() => setChartType("candle")}>
            Candles
          </ToggleButton>
          <ToggleButton active={chartType === "line"} onClick={() => setChartType("line")}>
            Line
          </ToggleButton>
        </div>
      </div>

      {summary && !loading && !error ? (
        <div className="mt-3 flex flex-wrap items-baseline gap-3">
          <span className="font-display text-2xl font-semibold">
            {formatCurrency(summary.latest)}
          </span>
          <span
            className={`text-sm font-medium ${
              summary.changePct >= 0 ? "text-emerald-700" : "text-rose-700"
            }`}
          >
            {summary.changePct >= 0 ? "+" : ""}
            {summary.changePct.toFixed(2)}% ({range})
          </span>
          {interval ? (
            <span className="text-xs uppercase tracking-[0.1em] text-ink-soft">
              {interval} bars
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="relative mt-3 rounded-xl border border-border bg-white">
        <div ref={containerRef} className="h-[320px] w-full" />
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-white/70 text-sm text-ink-soft">
            Loading {range} chart…
          </div>
        ) : null}
        {!loading && error ? (
          <div className="absolute inset-0 flex items-center justify-center rounded-xl px-4 text-center text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {!loading && !error && bars.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center rounded-xl text-sm text-ink-soft">
            No price data for this range.
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
        active
          ? "bg-accent-2 text-white"
          : "border border-border bg-white text-ink-soft hover:border-accent-2 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function dedupeSorted(bars: CandleBar[]): CandleBar[] {
  const sorted = [...bars].sort((a, b) => a.time - b.time);
  const output: CandleBar[] = [];
  let lastTime: number | null = null;
  for (const bar of sorted) {
    if (bar.time === lastTime) {
      output[output.length - 1] = bar; // keep the latest sample for a duplicate timestamp
      continue;
    }
    output.push(bar);
    lastTime = bar.time;
  }
  return output;
}

function summarize(bars: CandleBar[]): { latest: number; changePct: number } | null {
  if (bars.length === 0) {
    return null;
  }
  const start = bars[0].close;
  const latest = bars[bars.length - 1].close;
  const changePct = start === 0 ? 0 : ((latest - start) / start) * 100;
  return { latest, changePct };
}

function formatCurrency(value: number): string {
  return `₹${value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
