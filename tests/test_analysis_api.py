import os
import sys
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/stock_agent",
)

from backend.main import app
from backend.api.dependencies import get_analysis_service
from backend.models.schemas import AnalysisRequest


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_analysis_run_completes_and_returns_agent_reports():
    service = get_analysis_service()

    async def _run_flow():
        created = await service.create_analysis(
            AnalysisRequest(ticker="NVDA", timeframe="short"),
        )
        run_id = created.run_id

        for _ in range(80):
            payload = await service.get_analysis(run_id)
            if payload.status.value in {"completed", "partial_success", "failed"}:
                return payload
            await asyncio.sleep(0.05)
        return None

    final_payload = asyncio.run(_run_flow())
    assert final_payload is not None, "run did not reach terminal state in time"
    assert final_payload.status.value in {"completed", "partial_success"}
    assert final_payload.final_report is not None
    assert final_payload.final_report.final_verdict.value in {
        "buy",
        "hold",
        "sell",
        "no_recommendation",
    }

    reports = final_payload.agent_reports
    assert "technical_analysis" in reports
    assert "risk_analysis" in reports
    assert reports["technical_analysis"] is not None
    assert reports["risk_analysis"] is not None
