from __future__ import annotations

import json
from typing import Any

from backend.models.schemas import AgentReportEnvelope, AnalysisRunRecord
from backend.orchestrator.scoring import TIMEFRAME_WEIGHTS


SYSTEM_PROMPT = """You are a senior multi-factor equity strategist for Indian (NSE/BSE) stocks.
Synthesize the agent reports into ONE verdict for the run's timeframe, using only
the provided data. Do not invent missing facts. Decide on the WEIGHT OF EVIDENCE,
not unanimity.

WEIGHTING (by timeframe; the agents present vary by timeframe — reweight over
whichever agents are available and success-like):
- short:  technical 0.60, sentiment 0.25, fundamental 0.15
- medium: fundamental 0.40, technical 0.35, sentiment 0.15
- long:   fundamental 0.60, technical 0.20, sentiment 0.10
Sentiment is the noisiest input — use it as a tie-breaker, never a primary driver.

READ SIGNAL STRENGTH (do not treat weak == strong):
- Technical: MA alignment (ma20/ma50/ma200), MACD sign AND magnitude, RSI zones
  (>70 overbought, <30 oversold), volatility. trade_signal is a summary, not the
  whole story — weigh the underlying indicators.
- Fundamental: company_quality (strong/moderate/weak), valuation (under/fair/over),
  growth, margin, ROE, leverage (de_ratio).

RISK (asymmetric, risk-first):
- risk_level=high OR recommendation_constraint=block: do NOT issue BUY; a SELL
  (exit) is permitted and is often appropriate because exiting reduces risk. HOLD
  is acceptable only if the bearish case is weak.
- medium risk: directional calls are allowed, but lower the confidence.

QUANTITATIVE BASELINE:
- A quantitative_baseline is provided: a timeframe-weighted fusion of the agents'
  numeric scores (weighted_score in [-1, +1], a suggested_verdict and confidence).
  Treat it as your ANCHOR. Adopt it unless the agent detail clearly justifies an
  override, and keep your bias_score close to weighted_score (explain any divergence
  in decision_factors). This prevents conflicting signals from collapsing to HOLD.

VERDICT & CONVICTION:
- bias_score in [-1, +1] is your net directional conviction: negative = bearish,
  positive = bullish, magnitude = strength. It MUST be consistent with final_verdict
  (buy => bias_score > 0, sell => bias_score < 0, hold => near 0).
- Map conviction to verdict: bias_score >= +0.15 -> buy; <= -0.15 -> sell; otherwise
  hold. Conflicting-but-readable signals -> a directional call with lower confidence,
  or hold — NOT no_recommendation.
- Use no_recommendation ONLY when required agents are missing/failed, or data-quality
  flags make the read unreliable. Disagreement among agents is NOT a reason for it.

CONFIDENCE CALIBRATION:
- 0.80-1.00: strong weighted agreement AND strong signal magnitude.
- 0.60-0.80: a clear lean with minor conflict.
- 0.40-0.60: genuinely mixed (usually HOLD).
- < 0.40: weak or insufficient evidence.

Populate decision_factors with 3-5 weighted reasons, each citing the agent and the
specific signal. List real contradictions in conflicting_signals. Keep summary to
1-2 horizon-specific sentences. Return JSON matching the schema exactly.
"""

FINAL_VERDICT_PROMPT_VERSION = "v3.final_verdict.1"


def build_final_verdict_messages(
    *,
    run: AnalysisRunRecord,
    required_agents: list[str],
    selected_agents: list[str],
    success_like_selected: bool,
    baseline: dict | None = None,
) -> tuple[str, str]:
    report_payload: dict[str, Any] = {}
    for agent_name, report in run.agent_reports.items():
        if report is None:
            report_payload[agent_name] = None
            continue
        report_payload[agent_name] = _compact_report(report)

    user_payload = {
        "run_id": run.run_id,
        "target_type": run.target_type.value,
        "target_id": run.target_id,
        "timeframe": run.timeframe.value,
        "as_of": run.snapshot.as_of.isoformat() if run.snapshot else None,
        "required_agents": required_agents,
        "selected_agents": selected_agents,
        "success_like_selected": success_like_selected,
        "agent_weights": TIMEFRAME_WEIGHTS.get(run.timeframe.value, {}),
        "quantitative_baseline": baseline,
        "data_quality_flags": run.snapshot.data_quality_flags if run.snapshot else [],
        "agent_reports": report_payload,
        "policy_rules": [
            "Use no_recommendation ONLY if required agents are missing/failed or data "
            "quality is unreliable — never merely because agents disagree.",
            "High risk / recommendation_constraint=block: do not BUY, but SELL (exit) "
            "is permitted; HOLD only if the bearish case is weak.",
            "bias_score must agree in sign with final_verdict; lower confidence when "
            "signals conflict instead of defaulting to no_recommendation.",
        ],
    }
    return SYSTEM_PROMPT, json.dumps(user_payload, indent=2)


def _compact_report(report: AgentReportEnvelope) -> dict[str, Any]:
    # Pass the agent's full detail through to synthesis: its narrative summary,
    # all key points, every numeric signal, the structured result, the supporting
    # evidence (citations) and any errors — so the LLM reasons over the complete
    # picture rather than a thinned-out subset.
    return {
        "agent_name": report.agent_name,
        "status": report.status.value,
        "confidence": report.confidence,
        "summary": report.summary,
        "key_points": report.key_points,
        "signals": report.signals,
        "result": report.result,
        "citations": report.citations,
        "errors": report.errors,
    }
