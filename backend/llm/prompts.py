from __future__ import annotations

import json
from typing import Any

from backend.models.schemas import AgentReportEnvelope, AnalysisRunRecord


SYSTEM_PROMPT = """You are a senior investment strategist.

You must synthesize the provided agent outputs into one final verdict.
Use only the provided data.
Do not invent missing facts.
If evidence is insufficient or conflicting, return no_recommendation.
Respect risk-first decision making.
Return JSON that exactly matches the requested schema.
"""

FINAL_VERDICT_PROMPT_VERSION = "v1.final_verdict.1"


def build_final_verdict_messages(
    *,
    run: AnalysisRunRecord,
    required_agents: list[str],
    selected_agents: list[str],
    success_like_selected: bool,
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
        "data_quality_flags": run.snapshot.data_quality_flags if run.snapshot else [],
        "agent_reports": report_payload,
        "policy_rules": [
            "If required agents are missing or failed, use no_recommendation.",
            "If risk is high or recommendation_constraint is block, avoid buy/sell.",
            "Keep confidence conservative when signals conflict.",
        ],
    }
    return SYSTEM_PROMPT, json.dumps(user_payload, indent=2)


def _compact_report(report: AgentReportEnvelope) -> dict[str, Any]:
    return {
        "agent_name": report.agent_name,
        "status": report.status.value,
        "confidence": report.confidence,
        "summary": report.summary,
        "key_points": report.key_points,
        "signals": report.signals,
        "result": report.result,
        "errors": report.errors,
    }
