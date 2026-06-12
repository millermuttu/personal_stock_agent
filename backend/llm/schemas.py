from __future__ import annotations

from pydantic import BaseModel, Field

from backend.models.schemas import FinalVerdict, RiskLevel


class LLMSynthesisOutput(BaseModel):
    final_verdict: FinalVerdict
    # Net directional conviction in [-1, +1]: negative bearish, positive bullish,
    # magnitude = strength. Must stay consistent with final_verdict.
    bias_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    decision_factors: list[str] = Field(default_factory=list)
    conflicting_signals: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    summary: str


FINAL_VERDICT_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "final_verdict": {
            "type": "string",
            "enum": ["buy", "hold", "sell", "no_recommendation"],
        },
        "bias_score": {"type": "number", "minimum": -1.0, "maximum": 1.0},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
        "decision_factors": {"type": "array", "items": {"type": "string"}},
        "conflicting_signals": {"type": "array", "items": {"type": "string"}},
        "required_followups": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": [
        "final_verdict",
        "bias_score",
        "confidence",
        "risk_level",
        "decision_factors",
        "conflicting_signals",
        "required_followups",
        "summary",
    ],
}

