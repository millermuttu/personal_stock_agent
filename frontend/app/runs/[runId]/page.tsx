"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getAnalysis } from "../../../lib/api";
import type { AgentReportEnvelope, AnalysisRunResponse, NewsArticle } from "../../../lib/types";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { InvestPanel } from "./InvestPanel";
import { PriceChart } from "./PriceChart";

const TERMINAL_STATUSES = new Set(["completed", "partial_success", "failed"]);

export default function RunDetailsPage() {
  const params = useParams<{ runId: string }>();
  const runId = Array.isArray(params.runId) ? params.runId[0] : params.runId;

  const [run, setRun] = useState<AnalysisRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!runId) {
      return;
    }

    let cancelled = false;
    let timerId: number | null = null;

    const poll = async () => {
      try {
        const payload = await getAnalysis(runId);
        if (cancelled) {
          return;
        }
        setRun(payload);
        setRunError(null);
        setLoading(false);
        if (TERMINAL_STATUSES.has(payload.status)) {
          return;
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setRunError((error as Error).message);
        setLoading(false);
      }
      timerId = window.setTimeout(poll, 1400);
    };

    void poll();
    return () => {
      cancelled = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
    };
  }, [runId]);

  const providers = run?.snapshot?.providers ?? [];
  const qualityFlags = run?.snapshot?.data_quality_flags ?? [];
  const sentimentSignals = run?.snapshot?.features.sentiment_signals ?? {};
  const newsItems = run?.snapshot?.features.news_items ?? [];
  const newsArticles = run?.snapshot?.features.news_articles ?? [];
  const priceHistory = run?.snapshot?.features.price_history ?? [];
  const technicalIndicators = run?.snapshot?.features.technical_indicators ?? {};
  const fundamentalMetrics = run?.snapshot?.features.fundamental_metrics ?? {};
  const riskMetrics = run?.snapshot?.features.risk_metrics ?? {};
  const agentRows = run
    ? Object.entries(run.agent_reports).sort(([a], [b]) => a.localeCompare(b))
    : [];
  const finalVerdictClass = verdictClass(run?.final_report?.final_verdict);
  const priceSummary = summarizePriceSeries(priceHistory);

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 pb-12 pt-8 md:px-6">
      <section className="mb-6 animate-riseIn">
        <Link href="/" className="text-xs uppercase tracking-[0.2em] text-ink-soft underline">
          Back To Create
        </Link>
        <h1 className="mt-2 font-display text-3xl font-semibold leading-tight md:text-4xl">
          Run Details
        </h1>
        <p className="mt-2 text-sm text-ink-soft">
          {runId ? (
            <>
              Tracking <span className="font-mono text-ink">{runId}</span>
            </>
          ) : (
            "Missing run id in route."
          )}
        </p>
      </section>

      <section className="panel animate-riseIn p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-lg font-semibold">Execution Timeline</h2>
          <div className="flex items-center gap-2">
            <span className="chip">
              {run ? `status: ${run.status}` : loading ? "status: loading" : "status: unknown"}
            </span>
            {run?.status === "running" || run?.status === "queued" ? (
              <span className="chip border-accent/30 text-accent-2">polling</span>
            ) : null}
          </div>
        </div>
        <ExecutionTimeline run={run} loading={loading} runError={runError} />
        {run?.final_report ? (
          <div className={`mt-4 rounded-xl border px-4 py-3 ${finalVerdictClass}`}>
            <p className="text-xs font-semibold uppercase tracking-[0.12em]">Final Verdict</p>
            <p className="mt-1 font-display text-2xl font-semibold">
              {run.final_report.final_verdict.toUpperCase()}
            </p>
            <p className="mt-1 text-sm">Confidence: {(run.final_report.confidence * 100).toFixed(0)}%</p>
            {run.final_report.bias_score !== null ? (
              <ConvictionMeter score={run.final_report.bias_score} />
            ) : null}
            <p className="mt-2 text-xs uppercase tracking-[0.12em] text-ink-soft">
              Source: {run.final_report.synthesis_source}
            </p>
            {run.final_report.model_version ? (
              <p className="mt-1 text-xs text-ink-soft">
                Model: {run.final_report.model_version}
              </p>
            ) : null}
            {run.final_report.prompt_version ? (
              <p className="mt-1 text-xs text-ink-soft">
                Prompt: {run.final_report.prompt_version}
              </p>
            ) : null}
            {run.final_report.synthesis_source === "heuristic" &&
            run.final_report.llm_fallback_reason ? (
              <p className="mt-1 text-xs text-ink-soft">
                Fallback reason: {run.final_report.llm_fallback_reason}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      {run && (run.status === "completed" || run.status === "partial_success") ? (
        <section className="mt-4">
          <InvestPanel ticker={run.target_id} runId={run.run_id} />
        </section>
      ) : null}

      {run ? (
        <section className="mt-4 grid gap-4 md:grid-cols-[1.3fr_1fr]">
          <div className="panel animate-riseIn p-5 [animation-delay:80ms]">
            <h3 className="font-display text-lg font-semibold">Price Trend</h3>
            <p className="mt-1 text-xs uppercase tracking-[0.1em] text-ink-soft">
              Historical OHLC · {run.target_id}
            </p>
            <div className="mt-4">
              <PriceChart ticker={run.target_id} />
            </div>
          </div>
          <div className="panel animate-riseIn p-5 [animation-delay:100ms]">
            <h3 className="font-display text-lg font-semibold">Quick Stats</h3>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <MetricBadge label="Latest" value={formatCurrency(priceSummary.latest)} tone="neutral" />
              <MetricBadge label="Start" value={formatCurrency(priceSummary.start)} tone="neutral" />
              <MetricBadge
                label="Change"
                value={`${formatSignedPercent(priceSummary.changePct)}`}
                tone={priceSummary.changePct >= 0 ? "positive" : "negative"}
              />
              <MetricBadge label="Range Low" value={formatCurrency(priceSummary.low)} tone="neutral" />
              <MetricBadge label="Range High" value={formatCurrency(priceSummary.high)} tone="neutral" />
              <MetricBadge
                label="Final Risk"
                value={run.final_report?.risk_level ?? "unknown"}
                tone={riskTone(run.final_report?.risk_level)}
              />
            </div>
          </div>
        </section>
      ) : null}

      {run ? (
        <section className="mt-4 grid gap-4 md:grid-cols-3">
          <MetricPanel
            title="Technical Indicators"
            entries={orderedEntries(technicalIndicators, [
              "rsi",
              "macd_signal",
              "ma20",
              "ma50",
              "ma200",
              "bollinger_position",
              "volatility",
            ])}
            delayClass="[animation-delay:120ms]"
          />
          <MetricPanel
            title="Fundamental Metrics"
            entries={orderedEntries(fundamentalMetrics, [
              "revenue_growth",
              "profit_margin",
              "roe",
              "de_ratio",
              "pe_ratio",
              "fcf",
            ])}
            delayClass="[animation-delay:150ms]"
          />
          <MetricPanel
            title="Risk Metrics"
            entries={orderedEntries(riskMetrics, ["volatility", "beta", "max_drawdown"])}
            delayClass="[animation-delay:180ms]"
          />
        </section>
      ) : null}

      {run ? (
        <section className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="panel animate-riseIn p-5 [animation-delay:120ms]">
            <h3 className="font-display text-lg font-semibold">Snapshot Inputs</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {providers.map((provider) => (
                <span key={`${provider.name}-${provider.fetched_at}`} className="chip">
                  {provider.name}
                </span>
              ))}
              {providers.length === 0 ? <span className="chip">no providers yet</span> : null}
            </div>
            <p className="mt-4 text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft">
              Data Quality Flags
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {qualityFlags.length ? (
                qualityFlags.map((flag) => (
                  <span key={flag} className="chip border-amber-300 bg-amber-50 text-amber-900">
                    {flag}
                  </span>
                ))
              ) : (
                <span className="chip">none</span>
              )}
            </div>
          </div>

          <div className="panel animate-riseIn p-5 [animation-delay:160ms]">
            <h3 className="font-display text-lg font-semibold">Headline Sentiment Signals</h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {Object.entries(sentimentSignals).map(([key, value]) => (
                <div key={key} className="rounded-xl border border-border bg-white px-3 py-2 text-sm">
                  <p className="text-xs uppercase tracking-[0.1em] text-ink-soft">{key}</p>
                  <p className="mt-1 font-display text-lg">{value.toFixed(3)}</p>
                </div>
              ))}
              {Object.keys(sentimentSignals).length === 0 ? (
                <div className="rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink-soft">
                  No sentiment signals yet.
                </div>
              ) : null}
            </div>
            {newsArticles.length || newsItems.length ? (
              <>
                <p className="mt-4 text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft">
                  Headlines
                </p>
                <ul className="mt-2 space-y-2 text-sm">
                  {newsArticles.length
                    ? newsArticles.slice(0, 6).map((article, index) => (
                        <li key={`${article.title}-${index}`}>
                          <HeadlineItem article={article} />
                        </li>
                      ))
                    : newsItems.slice(0, 6).map((headline) => (
                        <li
                          key={headline}
                          className="rounded-lg border border-border px-3 py-2 text-ink-soft"
                        >
                          {headline}
                        </li>
                      ))}
                </ul>
              </>
            ) : null}
          </div>
        </section>
      ) : null}

      {run ? (
        <section className="mt-4 panel animate-riseIn p-5 [animation-delay:220ms]">
          <h3 className="font-display text-lg font-semibold">Agent Reports</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {agentRows.map(([agentName, report]) => (
              <AgentCard key={agentName} agentName={agentName} report={report} />
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}

function MetricPanel({
  title,
  entries,
  delayClass,
}: {
  title: string;
  entries: Array<[string, number]>;
  delayClass: string;
}) {
  return (
    <div className={`panel animate-riseIn p-5 ${delayClass}`}>
      <h3 className="font-display text-lg font-semibold">{title}</h3>
      <div className="mt-3 grid gap-2">
        {entries.length > 0 ? (
          entries.map(([key, value]) => (
            <MetricBadge
              key={key}
              label={metricLabel(key)}
              value={formatMetricValue(key, value)}
              tone={metricTone(key, value)}
            />
          ))
        ) : (
          <div className="rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink-soft">
            No metrics yet.
          </div>
        )}
      </div>
    </div>
  );
}

function MetricBadge({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "positive" | "negative" | "warning" | "neutral";
}) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${toneClass(tone)}`}>
      <p className="text-xs uppercase tracking-[0.1em]">{label}</p>
      <p className="mt-1 font-display text-lg">{value}</p>
    </div>
  );
}

function AgentCard({
  agentName,
  report,
}: {
  agentName: string;
  report: AgentReportEnvelope | null;
}) {
  if (!report) {
    return (
      <div className="rounded-xl border border-border bg-white p-4">
        <p className="font-display text-sm uppercase tracking-[0.1em] text-ink-soft">{agentName}</p>
        <p className="mt-1 text-sm text-ink-soft">No report yet.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="font-display text-sm uppercase tracking-[0.1em] text-ink-soft">{agentName}</p>
        <span className="chip border-accent/20 text-xs">{report.status}</span>
      </div>
      <p className="mt-2 text-sm">{report.summary}</p>
      <p className="mt-2 text-xs text-ink-soft">Confidence {(report.confidence * 100).toFixed(0)}%</p>
      {report.key_points.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs text-ink-soft">
          {report.key_points.slice(0, 3).map((point) => (
            <li key={point} className="rounded-md bg-canvas px-2 py-1">
              {point}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ConvictionMeter({ score }: { score: number }) {
  const clamped = Math.max(-1, Math.min(1, score));
  const pct = ((clamped + 1) / 2) * 100; // 50% = neutral
  const positive = clamped >= 0;
  const label = clamped > 0.05 ? "Bullish" : clamped < -0.05 ? "Bearish" : "Neutral";
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.1em] opacity-80">
        <span>Bearish</span>
        <span className="font-semibold">
          {label} · {clamped >= 0 ? "+" : ""}
          {clamped.toFixed(2)}
        </span>
        <span>Bullish</span>
      </div>
      <div className="relative mt-1 h-2 overflow-hidden rounded-full bg-white/60">
        <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-black/25" />
        <div
          className={`absolute top-0 h-full ${positive ? "bg-emerald-600" : "bg-rose-600"}`}
          style={
            positive
              ? { left: "50%", width: `${pct - 50}%` }
              : { left: `${pct}%`, width: `${50 - pct}%` }
          }
        />
      </div>
    </div>
  );
}

function HeadlineItem({ article }: { article: NewsArticle }) {
  const meta = [article.source, formatPublished(article.published_at)]
    .filter((part): part is string => !!part)
    .join(" · ");

  if (!article.url) {
    return (
      <div className="rounded-lg border border-border px-3 py-2">
        <p className="text-ink">{article.title}</p>
        {meta ? <p className="mt-0.5 text-xs text-ink-soft">{meta}</p> : null}
      </div>
    );
  }

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-lg border border-border px-3 py-2 transition hover:border-accent hover:bg-orange-50"
    >
      <p className="text-ink group-hover:text-accent">
        {article.title}
        <span aria-hidden className="ml-1 text-ink-soft group-hover:text-accent">
          ↗
        </span>
      </p>
      {meta ? <p className="mt-0.5 text-xs text-ink-soft">{meta}</p> : null}
    </a>
  );
}

function formatPublished(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function verdictClass(verdict: string | undefined): string {
  if (verdict === "buy") {
    return "border-emerald-300 bg-emerald-50 text-emerald-900";
  }
  if (verdict === "sell") {
    return "border-rose-300 bg-rose-50 text-rose-900";
  }
  if (verdict === "hold") {
    return "border-sky-300 bg-sky-50 text-sky-900";
  }
  return "border-amber-300 bg-amber-50 text-amber-900";
}

function orderedEntries(
  values: Record<string, number>,
  preferredOrder: string[],
): Array<[string, number]> {
  const emitted = new Set<string>();
  const output: Array<[string, number]> = [];
  for (const key of preferredOrder) {
    if (typeof values[key] === "number" && Number.isFinite(values[key])) {
      output.push([key, values[key]]);
      emitted.add(key);
    }
  }
  for (const [key, value] of Object.entries(values)) {
    if (emitted.has(key)) {
      continue;
    }
    if (typeof value !== "number" || !Number.isFinite(value)) {
      continue;
    }
    output.push([key, value]);
  }
  return output;
}

function summarizePriceSeries(values: number[]): {
  start: number;
  latest: number;
  low: number;
  high: number;
  changePct: number;
} {
  if (values.length === 0) {
    return { start: 0, latest: 0, low: 0, high: 0, changePct: 0 };
  }
  const start = values[0];
  const latest = values[values.length - 1];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const changePct = start === 0 ? 0 : ((latest - start) / start) * 100;
  return { start, latest, low, high, changePct };
}

function formatCurrency(value: number): string {
  return `₹${value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatSignedPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatMetricValue(key: string, value: number): string {
  if (key === "revenue_growth" || key === "profit_margin" || key === "roe" || key === "volatility" || key === "max_drawdown") {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (key === "fcf") {
    return `₹${value.toFixed(2)}B`;
  }
  return value.toFixed(3);
}

function metricLabel(key: string): string {
  const mapping: Record<string, string> = {
    rsi: "RSI",
    macd_signal: "MACD Signal",
    ma20: "MA20",
    ma50: "MA50",
    ma200: "MA200",
    bollinger_position: "Bollinger Pos",
    volatility: "Volatility",
    revenue_growth: "Revenue Growth",
    profit_margin: "Profit Margin",
    roe: "ROE",
    de_ratio: "Debt/Equity",
    pe_ratio: "P/E Ratio",
    fcf: "Free Cash Flow",
    beta: "Beta",
    max_drawdown: "Max Drawdown",
  };
  return mapping[key] ?? key;
}

function metricTone(key: string, value: number): "positive" | "negative" | "warning" | "neutral" {
  if (key === "revenue_growth" || key === "profit_margin" || key === "roe") {
    if (value > 0.08) {
      return "positive";
    }
    if (value < 0) {
      return "negative";
    }
    return "warning";
  }
  if (key === "de_ratio") {
    if (value > 1.8) {
      return "negative";
    }
    if (value > 1.0) {
      return "warning";
    }
    return "positive";
  }
  if (key === "max_drawdown") {
    if (value < -0.4) {
      return "negative";
    }
    if (value < -0.2) {
      return "warning";
    }
    return "positive";
  }
  if (key === "volatility") {
    if (value > 0.45) {
      return "negative";
    }
    if (value > 0.25) {
      return "warning";
    }
    return "positive";
  }
  if (key === "rsi") {
    if (value > 70 || value < 30) {
      return "warning";
    }
    return "positive";
  }
  return "neutral";
}

function riskTone(value: string | undefined): "positive" | "negative" | "warning" | "neutral" {
  if (value === "low") {
    return "positive";
  }
  if (value === "high") {
    return "negative";
  }
  if (value === "medium") {
    return "warning";
  }
  return "neutral";
}

function toneClass(tone: "positive" | "negative" | "warning" | "neutral"): string {
  if (tone === "positive") {
    return "border-emerald-300 bg-emerald-50 text-emerald-900";
  }
  if (tone === "negative") {
    return "border-rose-300 bg-rose-50 text-rose-900";
  }
  if (tone === "warning") {
    return "border-amber-300 bg-amber-50 text-amber-900";
  }
  return "border-border bg-white text-ink";
}
