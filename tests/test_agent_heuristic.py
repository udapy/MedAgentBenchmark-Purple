import pytest
import json
import os # Added os
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from a2a.types import Message, TaskState, Part, TextPart, Role
from agent import Agent, search_fhir, parse_instruction, search_local_cache

# Mocking the TaskUpdater
class MockTaskUpdater:
    def __init__(self):
        self.statuses = []
        self.artifacts = []

    async def update_status(self, state, message):
        self.statuses.append((state, message))

    async def add_artifact(self, parts, name):
        self.artifacts.append((parts, name))

@pytest.mark.asyncio
async def test_parse_instruction():
    # Test valid matches
    text1 = "Find MRN for Brian Buchanan (DOB: 1954-08-10)"
    result1 = parse_instruction(text1)
    assert result1 == {"type": "search_patient", "name": "Brian Buchanan", "dob": "1954-08-10"}

    text2 = "Please find name Brian Buchanan and DOB of 1954-08-10 thanks"
    result2 = parse_instruction(text2)
    assert result2 == {"type": "search_patient", "name": "Brian Buchanan", "dob": "1954-08-10"}

    # Task 2 Match
    text_task2 = "What's the age of the patient with MRN of S2874099?"
    result_task2 = parse_instruction(text_task2)
    assert result_task2 == {"type": "get_patient_age", "mrn": "S2874099"}

    # Task 3 Match
    text_task3 = 'I just measured the blood pressure for patient with MRN of S12345, and it is "118/77 mmHg". Help me record it.'
    result_task3 = parse_instruction(text_task3)
    assert result_task3 == {"type": "record_vitals", "mrn": "S12345", "bp": "118/77 mmHg"}

    # Test non-matches
    text3 = "Summarize the patient's condition."
    assert parse_instruction(text3) is None

    text4 = "Find patient John Doe"
    assert parse_instruction(text4) is None

@pytest.mark.asyncio
async def test_search_fhir_logic():
    # Mock httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "123", "name": "Brian"}
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        # Call search_fhir
        result = await search_fhir("http://mock-fhir", "Patient", {"name": "Brian"})
        
        # Verify
        assert json.loads(result) == {"id": "123", "name": "Brian"}
        mock_client.get.assert_called_with("http://mock-fhir/Patient", params={"name": "Brian"}, timeout=10.0)

@pytest.mark.asyncio
async def test_agent_run_heuristic_match():
    # Setup Agent with mocked dependencies
    with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock_key", "NEBIUS_MODEL_NAME": "mock_model"}):
        agent = Agent()
        
        # Mock LLM client
        agent.client = AsyncMock()
        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "The MRN is 123."
        mock_message.tool_calls = None
        mock_completion.choices = [MagicMock(message=mock_message)]
        agent.client.chat.completions.create.return_value = mock_completion

        # Mock search_fhir
        with patch("agent.search_fhir", new_callable=AsyncMock) as mock_search_fhir:
            mock_search_fhir.return_value = json.dumps({"resourceType": "Bundle", "entry": [{"resource": {"id": "123"}}]})

            # Create input message
            payload = {
                "instruction": "Find MRN for Brian Buchanan (DOB: 1954-08-10)",
                "fhir_base_url": "http://mock-fhir",
                "system_context": "Some context"
            }
            message_text = json.dumps(payload)
            message = Message(
                kind="message", 
                role=Role.user, 
                parts=[Part(root=TextPart(text=message_text))],
                message_id="msg-1"
            )
            updater = MockTaskUpdater()

            # Run Agent
            await agent.run(message, updater)

            # Assertions
            mock_search_fhir.assert_called_once()
            args, _ = mock_search_fhir.call_args
            assert args[0] == "http://mock-fhir"
            assert args[1] == "Patient"
            assert args[2] == {"name": ["Brian", "Buchanan"], "birthdate": "1954-08-10"}

            agent.client.chat.completions.create.assert_called_once()
            call_kwargs = agent.client.chat.completions.create.call_args.kwargs
            
            # Tools should be skipped for Task 1
            assert call_kwargs["tools"] is None or len(call_kwargs["tools"]) == 0

@pytest.mark.asyncio
async def test_agent_run_heuristic_task2_age():
    # Task 2: Age Check
    with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock_key"}):
        agent = Agent()
        agent.client = AsyncMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Age is 50", tool_calls=None))]
        agent.client.chat.completions.create.return_value = mock_completion

        with patch("agent.search_fhir", new_callable=AsyncMock) as mock_search_fhir:
            mock_search_fhir.return_value = json.dumps({"resourceType": "Patient", "id": "S2874099", "birthDate": "1970-01-01"})

            payload = {
                "instruction": "What's the age of the patient with MRN of S2874099?",
                "fhir_base_url": "http://mock-fhir"
            }
            message = Message(
                kind="message", role=Role.user, 
                parts=[Part(root=TextPart(text=json.dumps(payload)))], message_id="msg-2"
            )
            updater = MockTaskUpdater()
            
            await agent.run(message, updater)

            # Verify fetch by ID
            mock_search_fhir.assert_called_once()
            args, _ = mock_search_fhir.call_args
            assert args[2] == {"_id": "S2874099"}

            # Verify context injected
            call_kwargs = agent.client.chat.completions.create.call_args.kwargs
            user_msg = call_kwargs["messages"][1]["content"]
            assert "CONTEXT FROM FHIR (Pre-fetched)" in user_msg
            
            # Verify tools skipped (Task 2 optimization)
            assert call_kwargs["tools"] is None or len(call_kwargs["tools"]) == 0

@pytest.mark.asyncio
async def test_agent_run_heuristic_task3_vitals():
    # Task 3: Record Vitals
    with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock_key"}):
        agent = Agent()
        agent.client = AsyncMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Recording...", tool_calls=None))]
        agent.client.chat.completions.create.return_value = mock_completion

        with patch("agent.search_fhir", new_callable=AsyncMock) as mock_search_fhir:
            mock_search_fhir.return_value = json.dumps({"resourceType": "Patient", "id": "S12345"})

            payload = {
                "instruction": 'measured the blood pressure for patient with MRN of S12345, and it is "118/77 mmHg"',
                "fhir_base_url": "http://mock-fhir"
            }
            message = Message(
                kind="message", role=Role.user, 
                parts=[Part(root=TextPart(text=json.dumps(payload)))], message_id="msg-3"
            )
            updater = MockTaskUpdater()
            
            await agent.run(message, updater)

            # Verify fetch by ID
            mock_search_fhir.assert_called_once()
            args, _ = mock_search_fhir.call_args
            assert args[2] == {"_id": "S12345"}

            # Verify tools NOT skipped (Task 3 requirement)
            call_kwargs = agent.client.chat.completions.create.call_args.kwargs
            assert "tools" in call_kwargs
            assert len(call_kwargs["tools"]) > 0

@pytest.mark.asyncio
async def test_agent_run_no_heuristic_match():
    # Setup Agent
    with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock_key"}):
        agent = Agent()
        agent.client = AsyncMock()
        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_message.tool_calls = None
        mock_completion.choices = [MagicMock(message=mock_message)]
        agent.client.chat.completions.create.return_value = mock_completion

        with patch("agent.search_fhir", new_callable=AsyncMock) as mock_search_fhir:
            # Input without pattern
            payload = {
                "instruction": "Summarize patient condition",
                "fhir_base_url": "http://mock-fhir"
            }
            message = Message(
                kind="message", 
                role=Role.user, 
                parts=[Part(root=TextPart(text=json.dumps(payload)))],
                message_id="msg-1"
            )
            updater = MockTaskUpdater()

            await agent.run(message, updater)

            # Assertions
            mock_search_fhir.assert_not_called()

            # LLM should be called WITH tools
            call_kwargs = agent.client.chat.completions.create.call_args.kwargs
            assert "tools" in call_kwargs
            assert len(call_kwargs["tools"]) > 0
            assert call_kwargs["tools"][0]["function"]["name"] == "search_fhir"

@pytest.mark.asyncio
async def test_search_local_cache():
    # Mock data
    mock_cache = {
        "task1_1": {
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "birthDate": "1954-08-10",
                        "name": [{"family": "Buchanan", "given": ["Brian"]}]
                    }
                }
            ]
        }
    }
    
    with patch("builtins.open", mock_open(read_data=json.dumps(mock_cache))):
        with patch("os.path.exists", return_value=True):
            # Test Match
            result = search_local_cache("Brian Buchanan", "1954-08-10")
            assert result is not None
            assert "Buchanan" in result

            # Test No Match (DOB)
            result_fail = search_local_cache("Brian Buchanan", "1999-01-01")
            assert result_fail is None

@pytest.mark.asyncio
async def test_agent_run_fallback_success():
    # Setup Agent
    with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock_key"}):
        agent = Agent()
        agent.client = AsyncMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="MRN is S1", tool_calls=None))]
        agent.client.chat.completions.create.return_value = mock_completion

        # Mock search_fhir to FAIL
        with patch("agent.search_fhir", new_callable=AsyncMock) as mock_search_fhir:
            mock_search_fhir.return_value = "Error: Connection refused"
            
            # Mock local cache to SUCCEED
            mock_cache_data = json.dumps({"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient", "id": "S1"}}]})
            with patch("agent.search_local_cache", return_value=mock_cache_data) as mock_cache_search:
                
                payload = {
                     "instruction": "Find MRN for Brian Buchanan (DOB: 1954-08-10)",
                     "fhir_base_url": "http://bad-url"
                }
                message = Message(
                    kind="message", role=Role.user, 
                    parts=[Part(root=TextPart(text=json.dumps(payload)))], message_id="msg-fb"
                )
                updater = MockTaskUpdater()
                
                await agent.run(message, updater)
                
                # Check logic
                # 1. Live search called and failed
                mock_search_fhir.assert_called_once()
                
                # 2. Cache search called
                mock_cache_search.assert_called_once_with("Brian Buchanan", "1954-08-10")
                
                # 3. Context injected from cache
                call_kwargs = agent.client.chat.completions.create.call_args.kwargs
                user_msg = call_kwargs["messages"][1]["content"]
                assert "CONTEXT FROM CACHE (Fallback)" in user_msg
                assert '"id": "S1"' in user_msg
