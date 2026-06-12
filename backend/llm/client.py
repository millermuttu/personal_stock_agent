from __future__ import annotations

import json
import os

from openai import AsyncOpenAI

from backend.llm.prompts import build_final_verdict_messages
from backend.llm.schemas import FINAL_VERDICT_JSON_SCHEMA, LLMSynthesisOutput
from backend.models.schemas import AnalysisRunRecord


class LLMUnavailableError(Exception):
    pass


class LLMGenerationError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self._temperature = temperature
        if self._temperature is None:
            self._temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))

        self._is_enabled = bool(self._api_key)
        self._client = AsyncOpenAI(api_key=self._api_key) if self._is_enabled else None

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    @property
    def model_name(self) -> str:
        return self._model

    async def synthesize_final_verdict(
        self,
        *,
        run: AnalysisRunRecord,
        required_agents: list[str],
        selected_agents: list[str],
        success_like_selected: bool,
        baseline: dict | None = None,
    ) -> LLMSynthesisOutput:
        if not self._is_enabled or self._client is None:
            raise LLMUnavailableError("OPENAI_API_KEY is not configured")

        system_prompt, user_prompt = build_final_verdict_messages(
            run=run,
            required_agents=required_agents,
            selected_agents=selected_agents,
            success_like_selected=success_like_selected,
            baseline=baseline,
        )

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "final_verdict_schema",
                        "schema": FINAL_VERDICT_JSON_SCHEMA,
                        "strict": True,
                    },
                },
            )
        except Exception as exc:  # pylint: disable=broad-except
            raise LLMGenerationError(str(exc)) from exc

        message = completion.choices[0].message
        if message.content is None:
            raise LLMGenerationError("Model returned empty content")

        try:
            parsed = json.loads(message.content)
            return LLMSynthesisOutput.model_validate(parsed)
        except Exception as exc:  # pylint: disable=broad-except
            raise LLMGenerationError(f"Failed to parse model JSON output: {exc}") from exc
