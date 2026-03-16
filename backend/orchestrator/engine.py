from __future__ import annotations

import asyncio
from collections import Counter
from typing import Awaitable, Callable

from backend.agents import fundamental_analysis, risk_analysis, sentiment_analysis, technical_analysis
from backend.agents.common import build_agent_report
from backend.db.repositories import AgentWriteIsolationError, RunNotFoundError, RunRepository
from backend.llm.client import LLMClient, LLMGenerationError, LLMUnavailableError
from backend.llm.prompts import FINAL_VERDICT_PROMPT_VERSION
from backend.models.schemas import (
    AgentReportEnvelope,
    AgentStatus,
    DataSnapshot,
    FinalSynthesisSource,
    FinalVerdict,
    FinalVerdictReport,
    RecommendationConstraint,
    RiskLevel,
    RunStatus,
    utc_now,
)
from backend.orchestrator.policies import REQUIRED_AGENTS_BY_TIMEFRAME, is_success_like, selected_agents_for_timeframe
from backend.services.snapshot_builder import SnapshotBuilder


AgentWorker = Callable[..., Awaitable[AgentReportEnvelope]]


AGENT_REGISTRY: dict[str, AgentWorker] = {
    "technical_analysis": technical_analysis.run,
    "fundamental_analysis": fundamental_analysis.run,
    "sentiment_analysis": sentiment_analysis.run,
    "risk_analysis": risk_analysis.run,
}

HEURISTIC_SYNTHESIS_VERSION = "heuristic_v1"


class OrchestratorEngine:
    def __init__(
        self,
        repository: RunRepository,
        snapshot_builder: SnapshotBuilder,
        llm_client: LLMClient,
    ) -> None:
        self._repository = repository
        self._snapshot_builder = snapshot_builder
        self._llm_client = llm_client

    async def process_run(self, run_id: str) -> None:
        try:
            run = await self._repository.get_run(run_id)
        except RunNotFoundError:
            return

        try:
            await self._repository.update_status(run_id, RunStatus.RUNNING)
            snapshot = await self._snapshot_builder.build(run.target_id, run.timeframe)
            await self._repository.save_snapshot(run_id, snapshot)

            selected_agents = selected_agents_for_timeframe(run.timeframe)
            await self._repository.set_selected_agents(run_id, selected_agents)

            reports = await self._run_agents(
                run_id=run_id,
                ticker=run.target_id,
                timeframe=run.timeframe,
                snapshot=snapshot,
                selected_agents=selected_agents,
            )

            for report in reports:
                await self._repository.upsert_agent_report(
                    run_id,
                    actor_agent_name=report.agent_name,
                    report=report,
                )

            run = await self._repository.get_run(run_id)
            final_report, final_status = await self._synthesize_final_report(run)
            await self._repository.set_final_report(
                run_id,
                final_report,
                status=final_status,
            )
        except AgentWriteIsolationError as exc:
            await self._repository.update_status(
                run_id,
                RunStatus.FAILED,
                error_summary=f"agent write isolation failure: {exc}",
            )
        except Exception as exc:  # pylint: disable=broad-except
            await self._repository.update_status(
                run_id,
                RunStatus.FAILED,
                error_summary=f"orchestration failed: {exc}",
            )

    async def _run_agents(
        self,
        *,
        run_id: str,
        ticker: str,
        timeframe,
        snapshot: DataSnapshot,
        selected_agents: list[str],
    ) -> list[AgentReportEnvelope]:
        tasks = [
            self._run_single_agent(
                run_id=run_id,
                ticker=ticker,
                timeframe=timeframe,
                snapshot=snapshot,
                agent_name=agent_name,
            )
            for agent_name in selected_agents
        ]
        return list(await asyncio.gather(*tasks))

    async def _run_single_agent(
        self,
        *,
        run_id: str,
        ticker: str,
        timeframe,
        snapshot: DataSnapshot,
        agent_name: str,
    ) -> AgentReportEnvelope:
        worker = AGENT_REGISTRY[agent_name]
        try:
            return await worker(
                run_id=run_id,
                ticker=ticker,
                timeframe=timeframe,
                snapshot=snapshot,
            )
        except Exception as exc:  # pylint: disable=broad-except
            return build_agent_report(
                run_id=run_id,
                snapshot_id=snapshot.snapshot_id,
                agent_name=agent_name,
                ticker=ticker,
                timeframe=timeframe,
                as_of=snapshot.as_of,
                status=AgentStatus.FAILED,
                confidence=0.0,
                summary=f"{agent_name} failed during execution.",
                key_points=["Agent execution raised an exception."],
                signals={},
                result={},
                errors=[str(exc)],
            )

    async def _synthesize_final_report(self, run) -> tuple[FinalVerdictReport, RunStatus]:
        required_agents = REQUIRED_AGENTS_BY_TIMEFRAME[run.timeframe]
        selected_agents = run.selected_agents or selected_agents_for_timeframe(run.timeframe)
        reports = run.agent_reports

        missing_required = []
        for agent_name in required_agents:
            report = reports.get(agent_name)
            if report is None or not is_success_like(report.status):
                missing_required.append(agent_name)

        success_like_selected = all(
            (reports.get(agent_name) is not None and is_success_like(reports[agent_name].status))
            for agent_name in selected_agents
        )

        if missing_required:
            return self._no_recommendation_report(
                run=run,
                reason=f"Required agents missing or failed: {', '.join(missing_required)}",
                llm_fallback_reason="required_agents_missing_or_failed",
            ), RunStatus.PARTIAL_SUCCESS

        risk_level, risk_constraint = self._extract_risk_state(run)

        if risk_constraint == RecommendationConstraint.BLOCK:
            return self._no_recommendation_report(
                run=run,
                reason="Risk agent returned BLOCK constraint.",
                risk_level=risk_level,
                llm_fallback_reason="risk_constraint_blocked",
            ), (RunStatus.COMPLETED if success_like_selected else RunStatus.PARTIAL_SUCCESS)

        llm_fallback_reason: str | None = None
        if self._llm_client.is_enabled:
            try:
                llm_output = await self._llm_client.synthesize_final_verdict(
                    run=run,
                    required_agents=required_agents,
                    selected_agents=selected_agents,
                    success_like_selected=success_like_selected,
                )

                if llm_output.final_verdict in {FinalVerdict.BUY, FinalVerdict.SELL} and (
                    risk_constraint == RecommendationConstraint.BLOCK
                ):
                    return self._no_recommendation_report(
                        run=run,
                        reason="LLM returned directional verdict but risk constraints blocked action.",
                        risk_level=risk_level,
                        decision_factors=llm_output.decision_factors,
                        conflicting_signals=llm_output.conflicting_signals,
                    ), (RunStatus.COMPLETED if success_like_selected else RunStatus.PARTIAL_SUCCESS)

                final_report = FinalVerdictReport(
                    run_id=run.run_id,
                    target_id=run.target_id,
                    timeframe=run.timeframe,
                    as_of=run.snapshot.as_of if run.snapshot else utc_now(),
                    status=RunStatus.COMPLETED if success_like_selected else RunStatus.PARTIAL_SUCCESS,
                    final_verdict=llm_output.final_verdict,
                    synthesis_source=FinalSynthesisSource.LLM,
                    model_version=self._llm_client.model_name,
                    prompt_version=FINAL_VERDICT_PROMPT_VERSION,
                    llm_fallback_reason=None,
                    confidence=llm_output.confidence,
                    risk_level=llm_output.risk_level,
                    decision_factors=llm_output.decision_factors[:6],
                    conflicting_signals=llm_output.conflicting_signals,
                    required_followups=llm_output.required_followups,
                    summary=llm_output.summary,
                )
                return final_report, (RunStatus.COMPLETED if success_like_selected else RunStatus.PARTIAL_SUCCESS)
            except (LLMUnavailableError, LLMGenerationError) as exc:
                # Fall back to deterministic synthesis if the API is unavailable
                # or model output cannot be parsed safely.
                llm_fallback_reason = self._classify_llm_fallback_reason(exc)
        else:
            llm_fallback_reason = "llm_unavailable_no_api_key"

        return self._heuristic_synthesis(
            run,
            success_like_selected,
            risk_level,
            risk_constraint,
            llm_fallback_reason=llm_fallback_reason,
        )

    def _heuristic_synthesis(
        self,
        run,
        success_like_selected: bool,
        risk_level: RiskLevel,
        risk_constraint: RecommendationConstraint,
        *,
        llm_fallback_reason: str | None = None,
    ) -> tuple[FinalVerdictReport, RunStatus]:
        reports = run.agent_reports
        votes = []
        decision_factors = []

        tech_report = reports.get("technical_analysis")
        if tech_report is not None and is_success_like(tech_report.status):
            signal = tech_report.result.get("trade_signal")
            if signal in {"buy", "hold", "sell"}:
                votes.append(signal)
            decision_factors.extend(tech_report.key_points[:1])

        fundamental_report = reports.get("fundamental_analysis")
        if fundamental_report is not None and is_success_like(fundamental_report.status):
            signal = fundamental_report.result.get("investment_signal")
            if signal in {"buy", "hold", "sell"}:
                votes.append(signal)
            decision_factors.extend(fundamental_report.key_points[:1])

        sentiment_report = reports.get("sentiment_analysis")
        if sentiment_report is not None and is_success_like(sentiment_report.status):
            sentiment = sentiment_report.result.get("sentiment")
            if sentiment == "positive":
                votes.append("buy")
            elif sentiment == "negative":
                votes.append("sell")
            decision_factors.extend(sentiment_report.key_points[:1])

        conflicts = []
        if "buy" in votes and "sell" in votes:
            conflicts.append("bullish_and_bearish_signals_conflict")

        if not votes:
            return self._no_recommendation_report(
                run=run,
                reason="No valid directional votes available from agent outputs.",
                risk_level=risk_level,
                decision_factors=decision_factors,
                conflicting_signals=conflicts,
                llm_fallback_reason=llm_fallback_reason or "heuristic_no_directional_votes",
            ), (RunStatus.COMPLETED if success_like_selected else RunStatus.PARTIAL_SUCCESS)

        counts = Counter(votes)
        if counts["buy"] > max(counts["sell"], counts["hold"]):
            verdict = FinalVerdict.BUY
        elif counts["sell"] > max(counts["buy"], counts["hold"]):
            verdict = FinalVerdict.SELL
        else:
            verdict = FinalVerdict.HOLD

        final_report = FinalVerdictReport(
            run_id=run.run_id,
            target_id=run.target_id,
            timeframe=run.timeframe,
            as_of=run.snapshot.as_of if run.snapshot else utc_now(),
            status=RunStatus.COMPLETED if success_like_selected else RunStatus.PARTIAL_SUCCESS,
            final_verdict=verdict,
            synthesis_source=FinalSynthesisSource.HEURISTIC,
            model_version=None,
            prompt_version=HEURISTIC_SYNTHESIS_VERSION,
            llm_fallback_reason=llm_fallback_reason or "heuristic_policy",
            confidence=0.72 if verdict != FinalVerdict.NO_RECOMMENDATION else 0.45,
            risk_level=risk_level,
            decision_factors=decision_factors[:4],
            conflicting_signals=conflicts,
            required_followups=[],
            summary=f"Final verdict is {verdict.value} using synthesized agent signals with risk-first checks.",
        )
        return final_report, (RunStatus.COMPLETED if success_like_selected else RunStatus.PARTIAL_SUCCESS)

    @staticmethod
    def _extract_risk_state(run) -> tuple[RiskLevel, RecommendationConstraint]:
        risk_report = run.agent_reports.get("risk_analysis")
        risk_level = RiskLevel.UNKNOWN
        risk_constraint = RecommendationConstraint.CAUTION
        if risk_report is None:
            return risk_level, risk_constraint

        risk_level_raw = risk_report.result.get("risk_level", RiskLevel.UNKNOWN.value)
        constraint_raw = risk_report.result.get(
            "recommendation_constraint",
            RecommendationConstraint.CAUTION.value,
        )
        try:
            risk_level = RiskLevel(risk_level_raw)
        except ValueError:
            risk_level = RiskLevel.UNKNOWN
        try:
            risk_constraint = RecommendationConstraint(constraint_raw)
        except ValueError:
            risk_constraint = RecommendationConstraint.CAUTION
        return risk_level, risk_constraint

    @staticmethod
    def _no_recommendation_report(
        *,
        run,
        reason: str,
        risk_level: RiskLevel = RiskLevel.UNKNOWN,
        decision_factors: list[str] | None = None,
        conflicting_signals: list[str] | None = None,
        llm_fallback_reason: str | None = None,
    ) -> FinalVerdictReport:
        return FinalVerdictReport(
            run_id=run.run_id,
            target_id=run.target_id,
            timeframe=run.timeframe,
            as_of=run.snapshot.as_of if run.snapshot else utc_now(),
            status=RunStatus.PARTIAL_SUCCESS,
            final_verdict=FinalVerdict.NO_RECOMMENDATION,
            synthesis_source=FinalSynthesisSource.HEURISTIC,
            model_version=None,
            prompt_version=HEURISTIC_SYNTHESIS_VERSION,
            llm_fallback_reason=llm_fallback_reason,
            confidence=0.35,
            risk_level=risk_level,
            decision_factors=(decision_factors or []) + [reason],
            conflicting_signals=conflicting_signals or [],
            required_followups=["Collect fresher data and rerun required agents."],
            summary="System returned no_recommendation because safety/coverage thresholds were not met.",
        )

    @staticmethod
    def _classify_llm_fallback_reason(exc: Exception) -> str:
        text = str(exc).lower()
        if "insufficient_quota" in text or "exceeded your current quota" in text:
            return "llm_error_insufficient_quota"
        if "invalid_api_key" in text or "incorrect api key" in text:
            return "llm_error_invalid_api_key"
        if "rate limit" in text:
            return "llm_error_rate_limited"
        if "timeout" in text:
            return "llm_error_timeout"
        if "connection" in text or "connect call failed" in text:
            return "llm_error_connection"
        if "parse model json output" in text or "empty content" in text:
            return "llm_error_invalid_output"
        if "not configured" in text:
            return "llm_unavailable_no_api_key"
        return "llm_error_generation_failure"
