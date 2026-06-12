"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { listRuns } from "../../lib/api";
import type { AnalysisRunSummary, FinalVerdict, RunStatus, Timeframe } from "../../lib/types";

const TIMEFRAME_LABEL: Record<Timeframe, string> = {
  short: "Short",
  medium: "Medium",
  long: "Long",
};

export default function RunsHistoryPage() {
  const [runs, setRuns] = useState<AnalysisRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRuns(await listRuns(100));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 pb-12 pt-8 md:px-6">
      <section className="mb-6 flex flex-wrap items-end justify-between gap-3 animate-riseIn">
        <div>
          <p className="font-display text-xs uppercase tracking-[0.28em] text-ink-soft">History</p>
          <h1 className="mt-2 font-display text-3xl font-semibold leading-tight md:text-4xl">Runs</h1>
          <p className="mt-2 text-sm text-ink-soft">
            {runs.length
              ? `${runs.length} analysis ${runs.length === 1 ? "run" : "runs"}`
              : "Past analysis runs appear here."}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="rounded-xl border border-border bg-white px-3 py-2 text-sm font-medium text-ink-soft transition hover:border-accent hover:text-ink disabled:opacity-60"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
          <Link
            href="/"
            className="rounded-xl bg-accent px-3 py-2 text-sm font-semibold text-white transition hover:brightness-95"
          >
            New Analysis
          </Link>
        </div>
      </section>

      <section className="panel animate-riseIn overflow-hidden p-0">
        {error ? (
          <p className="px-5 py-4 text-sm text-rose-700">{error}</p>
        ) : loading && runs.length === 0 ? (
          <p className="px-5 py-6 text-sm text-ink-soft">Loading runs…</p>
        ) : runs.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-ink-soft">No runs yet.</p>
            <Link href="/" className="mt-2 inline-block text-sm font-semibold text-accent underline">
              Start your first analysis
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-[0.12em] text-ink-soft">
                  <th className="px-5 py-3 font-semibold">Stock</th>
                  <th className="px-5 py-3 font-semibold">Tenure</th>
                  <th className="px-5 py-3 font-semibold">Result</th>
                  <th className="px-5 py-3 font-semibold">Created</th>
                  <th className="px-5 py-3 font-semibold">Run ID</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.run_id}
                    className="group border-b border-border/70 transition last:border-0 hover:bg-orange-50/60"
                  >
                    <td className="px-5 py-3">
                      <Link href={`/runs/${run.run_id}`} className="block font-medium text-ink">
                        {run.target_id}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-ink-soft">{TIMEFRAME_LABEL[run.timeframe]}</td>
                    <td className="px-5 py-3">
                      <ResultBadge run={run} />
                    </td>
                    <td className="px-5 py-3 text-ink-soft">{formatDate(run.created_at)}</td>
                    <td className="px-5 py-3">
                      <Link
                        href={`/runs/${run.run_id}`}
                        className="font-mono text-xs text-ink-soft underline-offset-2 group-hover:text-accent group-hover:underline"
                      >
                        {run.run_id}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

function ResultBadge({ run }: { run: AnalysisRunSummary }) {
  // A finished verdict takes priority; otherwise reflect the run status.
  if (run.final_verdict) {
    const label =
      run.final_verdict === "no_recommendation" ? "NO REC" : run.final_verdict.toUpperCase();
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${verdictClass(
          run.final_verdict,
        )}`}
      >
        {label}
        {run.confidence !== null ? (
          <span className="font-normal opacity-70">{Math.round(run.confidence * 100)}%</span>
        ) : null}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${statusClass(
        run.status,
      )}`}
    >
      {(run.status === "running" || run.status === "queued") && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {run.status.replace("_", " ")}
    </span>
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

function statusClass(status: RunStatus): string {
  if (status === "failed") {
    return "border-rose-300 bg-rose-50 text-rose-700";
  }
  if (status === "partial_success") {
    return "border-amber-300 bg-amber-50 text-amber-800";
  }
  if (status === "running" || status === "queued") {
    return "border-accent/30 bg-orange-50 text-accent";
  }
  return "border-border bg-white text-ink-soft";
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }
  return parsed.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
