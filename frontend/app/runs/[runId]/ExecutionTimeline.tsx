"use client";

import type { AnalysisRunResponse } from "../../../lib/types";

type StageState = "pending" | "active" | "done" | "error";

const AGENT_LABELS: Record<string, string> = {
  technical_analysis: "Technical",
  fundamental_analysis: "Fundamental",
  sentiment_analysis: "Sentiment",
  risk_analysis: "Risk",
};

interface Stage {
  key: string;
  label: string;
  state: StageState;
  detail?: string;
}

export function ExecutionTimeline({
  run,
  loading,
  runError,
}: {
  run: AnalysisRunResponse | null;
  loading: boolean;
  runError: string | null;
}) {
  const stages = computeStages(run);
  const doneCount = stages.filter((stage) => stage.state === "done").length;
  const hasError = stages.some((stage) => stage.state === "error");
  // Fill the bar through completed stages, plus a half-step for an active one.
  const activeBoost = stages.some((stage) => stage.state === "active") ? 0.5 : 0;
  const progressPct = stages.length
    ? Math.min(100, ((doneCount + activeBoost) / stages.length) * 100)
    : 0;

  const agentEntries = run
    ? Object.entries(run.agent_reports).sort(([a], [b]) => a.localeCompare(b))
    : [];
  const selectionKnown = (run?.selected_agents?.length ?? 0) > 0;
  const selectedSet = new Set(run?.selected_agents ?? []);

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between text-xs text-ink-soft">
        <span className="font-semibold uppercase tracking-[0.12em]">Progress</span>
        <span>{Math.round(progressPct)}%</span>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-canvas">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ease-out ${
            hasError ? "bg-rose-500" : "bg-accent-2"
          }`}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      <ol className="mt-5 flex flex-col gap-3 md:flex-row md:items-stretch md:gap-0">
        {stages.map((stage, index) => (
          <li key={stage.key} className="flex items-center md:flex-1">
            <StageNode stage={stage} index={index} />
            {index < stages.length - 1 ? <Connector nextState={stages[index + 1].state} /> : null}
          </li>
        ))}
      </ol>

      {agentEntries.length > 0 ? (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft">
            Agents
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {agentEntries.map(([name, report]) => {
              const skipped = selectionKnown && !selectedSet.has(name);
              if (skipped) {
                return (
                  <span
                    key={name}
                    title="Not used for this timeframe"
                    className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-border bg-white px-3 py-1 text-xs text-ink-soft/70"
                  >
                    <span className="h-2 w-2 rounded-full bg-slate-300" />
                    {AGENT_LABELS[name] ?? name}
                    <span className="opacity-70">· skipped</span>
                  </span>
                );
              }
              const state = agentChipState(report?.status ?? null, run?.status);
              return (
                <span
                  key={name}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${chipClass(
                    state,
                  )}`}
                >
                  <Dot state={state} />
                  {AGENT_LABELS[name] ?? name}
                  {report?.status ? (
                    <span className="opacity-70">· {report.status}</span>
                  ) : (
                    <span className="opacity-70">· {state === "active" ? "running" : "pending"}</span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      ) : null}

      {run?.error_summary ? (
        <p className="mt-4 rounded-xl border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {run.error_summary}
        </p>
      ) : null}
      {runError ? (
        <p className="mt-3 rounded-xl border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {runError}
        </p>
      ) : null}
      {!run && loading ? (
        <p className="mt-3 text-sm text-ink-soft">Loading run status…</p>
      ) : null}
    </div>
  );
}

function StageNode({ stage, index }: { stage: Stage; index: number }) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm font-semibold ${nodeClass(
          stage.state,
        )}`}
      >
        {stage.state === "done" ? "✓" : stage.state === "error" ? "!" : index + 1}
      </span>
      <div className="leading-tight">
        <p className={`text-sm font-medium ${labelClass(stage.state)}`}>{stage.label}</p>
        {stage.detail ? <p className="text-xs text-ink-soft">{stage.detail}</p> : null}
      </div>
    </div>
  );
}

function Connector({ nextState }: { nextState: StageState }) {
  const reached = nextState === "done" || nextState === "active" || nextState === "error";
  const color = nextState === "error" ? "bg-rose-400" : reached ? "bg-accent-2" : "bg-border";
  return (
    <span className="mx-3 hidden h-[2px] flex-1 items-center md:flex">
      <span className={`h-[2px] w-full rounded-full ${color}`} />
    </span>
  );
}

function Dot({ state }: { state: StageState }) {
  const color =
    state === "done"
      ? "bg-emerald-500"
      : state === "active"
        ? "bg-accent animate-pulse"
        : state === "error"
          ? "bg-rose-500"
          : "bg-slate-300";
  return <span className={`h-2 w-2 rounded-full ${color}`} />;
}

function computeStages(run: AnalysisRunResponse | null): Stage[] {
  const status = run?.status;
  const snapshotDone = !!run?.snapshot;
  // Only agents selected for this timeframe actually run; the API seeds all
  // slots, so count against the selected set (falling back to all known slots
  // before selection happens).
  const reports = run?.agent_reports ?? {};
  const selected = run?.selected_agents ?? [];
  const relevantAgents = selected.length > 0 ? selected : Object.keys(reports);
  const agentTotal = relevantAgents.length;
  const agentDoneCount = relevantAgents.filter((name) => reports[name] != null).length;
  const agentsDone = agentTotal > 0 && agentDoneCount === agentTotal;
  const finalDone = !!run?.final_report;
  const failed = status === "failed";

  // Ordered completion flags drive which stage is currently active.
  const completion = [
    status !== undefined && status !== "queued", // queued accepted
    snapshotDone,
    agentsDone,
    finalDone,
  ];
  const firstIncomplete = completion.indexOf(false);

  const stateFor = (index: number): StageState => {
    if (!run) {
      return "pending";
    }
    if (firstIncomplete === -1) {
      return "done";
    }
    if (index < firstIncomplete) {
      return "done";
    }
    if (index === firstIncomplete) {
      return failed ? "error" : "active";
    }
    return failed ? "error" : "pending";
  };

  return [
    { key: "queued", label: "Queued", state: stateFor(0) },
    {
      key: "snapshot",
      label: "Data Snapshot",
      state: stateFor(1),
      detail: snapshotDone ? "Market · fundamentals · news" : "Fetching market data",
    },
    {
      key: "agents",
      label: "Agent Analysis",
      state: stateFor(2),
      detail: agentTotal > 0 ? `${agentDoneCount}/${agentTotal} complete` : undefined,
    },
    {
      key: "final",
      label: "Final Verdict",
      state: stateFor(3),
      detail: finalDone ? run?.final_report?.final_verdict.toUpperCase() : "Synthesizing",
    },
  ];
}

function agentChipState(status: string | null, runStatus: string | undefined): StageState {
  if (status === null) {
    return runStatus === "running" ? "active" : runStatus === "queued" ? "pending" : "pending";
  }
  if (status === "success") {
    return "done";
  }
  if (status === "failed") {
    return "error";
  }
  // partial_success / insufficient_data
  return "active";
}

function nodeClass(state: StageState): string {
  if (state === "done") {
    return "border-emerald-400 bg-emerald-500 text-white";
  }
  if (state === "active") {
    return "border-accent bg-accent text-white animate-pulse";
  }
  if (state === "error") {
    return "border-rose-400 bg-rose-500 text-white";
  }
  return "border-border bg-white text-ink-soft";
}

function labelClass(state: StageState): string {
  if (state === "done") {
    return "text-emerald-800";
  }
  if (state === "active") {
    return "text-accent";
  }
  if (state === "error") {
    return "text-rose-700";
  }
  return "text-ink-soft";
}

function chipClass(state: StageState): string {
  if (state === "done") {
    return "border-emerald-300 bg-emerald-50 text-emerald-800";
  }
  if (state === "active") {
    return "border-accent/40 bg-orange-50 text-accent";
  }
  if (state === "error") {
    return "border-rose-300 bg-rose-50 text-rose-700";
  }
  return "border-border bg-white text-ink-soft";
}
