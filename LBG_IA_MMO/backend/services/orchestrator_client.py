import os

import httpx
from pydantic import ValidationError

from models.intents import IntentRequest, IntentResponse


class OrchestratorError(RuntimeError):
    pass


class OrchestratorClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_env(cls) -> "OrchestratorClient":
        base_url = os.environ.get("LBG_ORCHESTRATOR_URL", "http://localhost:8010")
        return cls(base_url=base_url)

    @staticmethod
    def _timeout_s() -> float:
        """
        L'orchestrator peut appeler des agents (LLM/Ollama) et prendre > 10s.
        Sur VM (systemd), on préfère un timeout plus large et configurable.
        """
        raw = os.environ.get("LBG_ORCHESTRATOR_TIMEOUT", "180").strip()
        try:
            return max(5.0, float(raw))
        except ValueError:
            return 180.0

    async def route_intent(self, payload: IntentRequest) -> IntentResponse:
        url = f"{self._base_url}/v1/route"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s()) as client:
                r = await client.post(url, json=payload.model_dump())
        except httpx.TimeoutException as e:
            raise OrchestratorError(f"Timeout calling orchestrator at {url}: {e}") from e
        except httpx.RequestError as e:
            raise OrchestratorError(f"Error calling orchestrator at {url}: {type(e).__name__}: {e}") from e

        if r.status_code >= 400:
            body_preview = (r.text or "")[:2000]
            raise OrchestratorError(f"Orchestrator returned {r.status_code}: {body_preview}")

        try:
            data = r.json()
        except ValueError as e:
            body_preview = (r.text or "")[:2000]
            raise OrchestratorError(f"Invalid JSON from orchestrator: {body_preview}") from e

        try:
            return IntentResponse.model_validate(data)
        except ValidationError as e:
            raise OrchestratorError(f"Unexpected orchestrator payload shape: {e}") from e

