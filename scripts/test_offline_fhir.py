import asyncio
import json
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from agent import Agent
from a2a.types import Message, Part, TextPart, Role, TaskState
from a2a.utils import new_agent_text_message

# Mock TaskUpdater
class MockUpdater:
    async def update_status(self, state, message):
        text = ""
        if message.parts and message.parts[0].root:
             text = message.parts[0].root.text
        print(f"[STATUS UPDATE] {state}: {text}")

    async def add_artifact(self, parts, name):
        print(f"\n[ARTIFACT] {name}:")
        for part in parts:
            if isinstance(part.root, TextPart):
                print(part.root.text)

async def run_test(agent, instruction, msg_id):
    print(f"\n--- Testing Instruction: {instruction} ---")
    payload = {
        "instruction": instruction,
        "fhir_base_url": "http://localhost:8080/fhir",
        "system_context": "This is a offline test run."
    }
    
    message_text = json.dumps(payload)
    message = Message(
        kind="message",
        role=Role.user,
        parts=[Part(root=TextPart(text=message_text))],
        message_id=msg_id
    )
    
    updater = MockUpdater()
    await agent.run(message, updater)

async def main():
    print("Initializing Agent...")
    agent = Agent()
    
    # Test cases
    # 1. Task 1 (Patient Search)
    await run_test(agent, "Find MRN for Maria Alvarez (DOB: 1940-03-05)", "msg-1")
    
    # 2. Task 2 (Age Check) - Using MRN S6426560 (Maria Alvarez's MRN from Task 1)
    await run_test(agent, "What's the age of the patient with MRN of S6426560?", "msg-2")
    
    # 3. Task 3 (Record Vitals)
    await run_test(agent, 'measured the blood pressure for patient with MRN of S6426560, and it is "118/77 mmHg". Help me record it.', "msg-3")

if __name__ == "__main__":
    asyncio.run(main())
