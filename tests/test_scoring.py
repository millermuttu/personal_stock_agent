import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.models.schemas import AgentStatus, Timeframe
from backend.orchestrator.scoring import compute_quant_baseline


def _rep(score, confidence=0.7):
    return SimpleNamespace(
        status=AgentStatus.SUCCESS, confidence=confidence, result={"score": score}
    )


def test_strong_fundamental_outweighs_mild_technical_no_hold_collapse():
    # Strong fundamental buy + mild technical sell used to net to HOLD under the
    # categorical vote. Weighted fusion should now resolve to a directional BUY.
    reports = {
        "fundamental_analysis": _rep(0.6, 0.7),
        "technical_analysis": _rep(-0.3, 0.68),
        "sentiment_analysis": _rep(0.2, 0.6),
    }
    baseline = compute_quant_baseline(reports, Timeframe.MEDIUM)
    assert baseline is not None
    assert baseline["weighted_score"] > 0
    assert baseline["suggested_verdict"] == "buy"


def test_aligned_bearish_yields_sell_and_negative_bias():
    reports = {
        "technical_analysis": _rep(-0.8, 0.68),
        "sentiment_analysis": _rep(-0.5, 0.6),
    }
    baseline = compute_quant_baseline(reports, Timeframe.SHORT)
    assert baseline is not None
    assert baseline["suggested_verdict"] == "sell"
    assert baseline["weighted_score"] < 0


def test_no_directional_scores_returns_none():
    reports = {
        "technical_analysis": SimpleNamespace(
            status=AgentStatus.SUCCESS, confidence=0.7, result={}
        ),
    }
    assert compute_quant_baseline(reports, Timeframe.SHORT) is None


def test_failed_agents_are_excluded():
    reports = {
        "technical_analysis": SimpleNamespace(
            status=AgentStatus.FAILED, confidence=0.0, result={"score": -0.9}
        ),
        "fundamental_analysis": _rep(0.5, 0.7),
    }
    baseline = compute_quant_baseline(reports, Timeframe.LONG)
    assert baseline is not None
    # Only the successful (bullish) fundamental contributes.
    assert baseline["weighted_score"] > 0
    assert "technical_analysis" not in baseline["contributions"]
