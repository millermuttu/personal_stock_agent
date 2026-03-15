import asyncio

import pytest

from backend.llm.client import LLMClient, LLMUnavailableError


def test_llm_client_disabled_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = LLMClient(api_key=None)
    assert client.is_enabled is False

    async def _invoke():
        with pytest.raises(LLMUnavailableError):
            await client.synthesize_final_verdict(
                run=None,  # type: ignore[arg-type]
                required_agents=[],
                selected_agents=[],
                success_like_selected=False,
            )

    asyncio.run(_invoke())

