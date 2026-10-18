"""Writes with a model deployed in Microsoft Foundry, through Microsoft Agent Framework.

The Storyteller, Persona and Recap each become an Agent Framework `Agent` with
their system prompt as instructions, all sharing one Foundry chat client. The
other four agents are plain code and never call a model.

Sign-in is Microsoft Entra ID, so there are no keys to keep: `az login` on a
laptop, the app's managed identity when it runs on Azure. Either way the
identity needs the Foundry User role on the Foundry resource.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

TIMEOUT_S = 20.0  # a story that takes longer than this is too late for live TV anyway

# A failed sign-in is reported once per call in the agent trace; azure-identity would also log each attempt.
logging.getLogger("azure.identity").setLevel(logging.ERROR)


def credential() -> Any:
    """The app's managed identity on Azure (Container Apps sets IDENTITY_ENDPOINT), the Azure CLI sign-in elsewhere."""
    from azure.identity.aio import AzureCliCredential, ManagedIdentityCredential

    if os.environ.get("IDENTITY_ENDPOINT"):
        return ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID") or None)
    return AzureCliCredential()


class FoundryModel:
    def __init__(self, endpoint: str = "", model: str = "", reasoning_effort: str = "low", client: Any = None):
        self.name = model or "foundry"
        self.client = client or FoundryChatClient(project_endpoint=endpoint, model=model, credential=credential())
        # store=False: each line is a one-off, so nothing needs keeping server-side as a conversation.
        self.options: dict[str, Any] = {"store": False}
        if reasoning_effort:
            self.options["reasoning"] = {"effort": reasoning_effort}
        self.agents: dict[str, Agent] = {}

    def agent(self, name: str, instructions: str) -> Agent:
        if name not in self.agents:
            self.agents[name] = Agent(self.client, instructions, name=name, default_options=self.options)
        return self.agents[name]

    async def complete(self, agent: str, system: str, prompt: str, context: dict) -> str:
        response = await asyncio.wait_for(self.agent(agent, system).run(prompt), TIMEOUT_S)
        text = response.text.strip()
        if not text:
            raise RuntimeError(f"{self.name} sent back no text")
        return text
