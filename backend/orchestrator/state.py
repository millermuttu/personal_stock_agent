from __future__ import annotations

from typing import TypedDict


class OrchestratorState(TypedDict):
    run_id: str
    agent_reports: dict[str, object | None]


def apply_agent_report_patch(
    *,
    current_reports: dict[str, object | None],
    actor_agent_name: str,
    payload: object,
) -> dict[str, object | None]:
    """Apply a key-based patch that can only update one agent slot.

    This preserves write isolation so one agent cannot overwrite another
    agent's report in orchestrator state.
    """

    if actor_agent_name not in current_reports:
        raise ValueError(f"unknown agent slot: {actor_agent_name}")

    next_reports = dict(current_reports)
    next_reports[actor_agent_name] = payload
    return next_reports

