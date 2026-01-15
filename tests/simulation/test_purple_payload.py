import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agent import Agent
from a2a.types import Message, TaskState, Part, TextPart
from a2a.server.tasks import TaskUpdater

# Mock TaskUpdater
class MockUpdater:
    def __init__(self):
        self.status = []
        self.artifacts = []

    async def update_status(self, state, message):
        self.status.append((state, message))

    async def add_artifact(self, parts, name):
        self.artifacts.append((parts, name))

@pytest.mark.asyncio
async def test_agent_payload_fhir_flow():
    # Mock inputs
    payload = {
        "instruction": "Find the patient Brian Buchanan",
        "system_context": "Current time is 2023-11-13",
        "fhir_base_url": "http://mock-fhir:8080/fhir",
        "interaction_limit": 5
    }
    input_text = json.dumps(payload)
    
    msg = Message(
        kind="message",
        role="user",
        parts=[Part(root=TextPart(kind="text", text=input_text))],
        message_id="test-id",
        context_id="ctx-id"
    )
    
    updater = MockUpdater()
    agent = Agent()
    
    # Mock OpenAI client and search_fhir
    agent.client = AsyncMock()
    
    # Mock the LLM responses
    # First response: Call tool
    tool_call_function = MagicMock()
    tool_call_function.name = "search_fhir"
    tool_call_function.arguments = json.dumps({"resource_type": "Patient", "params": {"given": "Brian", "family": "Buchanan"}})
    
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function = tool_call_function
    
    tool_call_msg = MagicMock()
    tool_call_msg.tool_calls = [tool_call]
    tool_call_msg.content = None
    
    # Second response: Final answer
    final_msg = MagicMock()
    final_msg.tool_calls = None
    final_msg.content = "found patient Brian Buchanan"
    
    agent.client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=tool_call_msg)]),
        MagicMock(choices=[MagicMock(message=final_msg)])
    ]
    
    # Mock httpx for search_fhir
    with patch("src.agent.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value.json.return_value = {"resourceType": "Bundle", "entry": [{"resource": {"id": "123"}}]}
        mock_client.get.return_value.raise_for_status = MagicMock()
        
        await agent.run(msg, updater)
        
        # Verify FHIR call
        mock_client.get.assert_called_with(
            "http://mock-fhir:8080/fhir/Patient",
            params={"given": "Brian", "family": "Buchanan"},
            timeout=10.0
        )
        
        # Verify Artifact created
        assert len(updater.artifacts) == 1
        assert updater.artifacts[0][1] == "Response"
        assert updater.artifacts[0][0][0].root.text == "found patient Brian Buchanan"

if __name__ == "__main__":
    asyncio.run(test_agent_payload_fhir_flow())
