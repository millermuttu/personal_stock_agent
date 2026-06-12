"""Continuous signal fusion for the final verdict.

Each directional agent emits a `score` in [-1, +1] (bearish .. bullish). This
module fuses them into a single timeframe-weighted baseline so that conflicting
signals resolve by *magnitude* instead of collapsing to HOLD. The result is used
directly by the deterministic heuristic and handed to the LLM as a quantitative
anchor.
"""
from __future__ import annotations

from typing import Any

from backend.models.schemas import FinalVerdict, Timeframe
from backend.orchestrator.policies import is_success_like

# Per-timeframe weights over the directional agents (risk is a gate, not a vote).
TIMEFRAME_WEIGHTS: dict[str, dict[str, float]] = {
    "short": {"technical_analysis": 0.60, "sentiment_analysis": 0.25, "fundamental_analysis": 0.15},
    "medium": {"fundamental_analysis": 0.40, "technical_analysis": 0.35, "sentiment_analysis": 0.15},
    "long": {"fundamental_analysis": 0.60, "technical_analysis": 0.20, "sentiment_analysis": 0.10},
}

DIRECTIONAL_AGENTS = ("technical_analysis", "fundamental_analysis", "sentiment_analysis")

BUY_THRESHOLD = 0.15
SELL_THRESHOLD = -0.15


def verdict_from_score(score: float) -> FinalVerdict:
    if score >= BUY_THRESHOLD:
        return FinalVerdict.BUY
    if score <= SELL_THRESHOLD:
        return FinalVerdict.SELL
    return FinalVerdict.HOLD


def compute_quant_baseline(reports: dict, timeframe: Timeframe) -> dict[str, Any] | None:
    """Weighted fusion of agent scores. Returns None if no directional signal.

    weighted_score = Σ(score · weight · confidence) / Σ(weight · confidence)
    """
    weights = TIMEFRAME_WEIGHTS.get(timeframe.value, {})
    contributions: dict[str, dict[str, float]] = {}
    numerator = 0.0
    denominator = 0.0

    for agent_name in DIRECTIONAL_AGENTS:
        report = reports.get(agent_name)
        if report is None or not is_success_like(report.status):
            continue
        raw_score = report.result.get("score")
        if not isinstance(raw_score, (int, float)):
            continue
        score = max(-1.0, min(1.0, float(raw_score)))
        weight = weights.get(agent_name, 0.0) * float(report.confidence)
        if weight <= 0:
            continue
        numerator += score * weight
        denominator += weight
        contributions[agent_name] = {"score": round(score, 4), "weight": round(weight, 4)}

    if denominator == 0:
        return None

    weighted = numerator / denominator
    verdict = verdict_from_score(weighted)

    # Agreement = share of weight whose sign matches the net direction.
    aligned = sum(
        c["weight"] for c in contributions.values() if (c["score"] >= 0) == (weighted >= 0)
    )
    agreement = aligned / denominator if denominator else 0.0
    confidence = round(min(0.95, 0.40 + 0.35 * abs(weighted) + 0.20 * agreement), 2)

    return {
        "weighted_score": round(weighted, 4),
        "suggested_verdict": verdict.value,
        "confidence": confidence,
        "agreement": round(agreement, 4),
        "contributions": contributions,
    }
