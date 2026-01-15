import asyncio
import httpx
import json
import uuid
import pytest

AGENT_URL = "http://localhost:9010"
FHIR_URL = "http://localhost:8080/fhir"

@pytest.mark.asyncio
async def test_integration():
    print(f"Testing integration with Agent at {AGENT_URL} and FHIR at {FHIR_URL}")
    
    # 1. Construct Payload
    payload = {
        "instruction": "What is the MRN of the patient with name Brian Buchanan and DOB of 1954-08-10?",
        "system_context": "Current time is 2026-01-15T12:00:00+00:00",
        "fhir_base_url": FHIR_URL,
        "interaction_limit": 5
    }
    
    message = {
        "kind": "message",
        "role": "user",
        "parts": [{
            "text": json.dumps(payload),
            "kind": "text"
        }],
        "message_id": uuid.uuid4().hex,
        "context_id": uuid.uuid4().hex
    }
    
    # 2. Add 'tools' capability if A2A protocol requires it in handshake, 
    # but simplest is just hitting the /message endpoint.
    # The A2A server exposes /message/send usually.
    # Let's check server.py routes if needed, but assuming standard A2A.
    # Actually, a2a-sdk servers usually listen on /message/send or similar.
    # Let's inspect src/server.py to be sure about the endpoint.
    
    # However, A2A clients usually handle the endpoint. 
    # Let's assume standard A2A endpoint: POST /
    # But wait, a2a-sdk usually runs a FastMCP like server or HTTP server.
    # Let's verify src/server.py contents first or just try standard ways.
    # Standard A2A HTTP server usually exposes POST /messages or similar.
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First, check health/card
        try:
            resp = await client.get(f"{AGENT_URL}/card")
            print(f"Agent Card: {resp.status_code}")
        except Exception as e:
            pytest.skip(f"Skipping integration test: Failed to connect to agent at {AGENT_URL}. Error: {e}")
            return

        # Send Message
        # Using the A2A client library would be safer, but raw HTTP is fine if we know the protocol.
        # But wait, src/messenger.py uses A2A client.
        # Let's use the same simpler approach as client/app.py if possible, or just use the a2a client.
        
        from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
        from a2a.types import Message, Part, TextPart
        
        resolver = A2ACardResolver(httpx_client=client, base_url=AGENT_URL)
        agent_card = await resolver.get_agent_card()
        config = ClientConfig(httpx_client=client, streaming=False)
        factory = ClientFactory(config)
        a2a_client = factory.create(agent_card)
        
        outbound_msg = Message(
            kind="message",
            role="user",
            parts=[Part(TextPart(kind="text", text=json.dumps(payload)))],
            message_id=uuid.uuid4().hex,
            context_id=uuid.uuid4().hex
        )
        
        print("Sending message...")
        responses = []
        async for event in a2a_client.send_message(outbound_msg):
            # print(f"Event: {type(event)}")
            if isinstance(event, Message):
                responses.append(event)
            elif hasattr(event, "status") and event.status.message:
                 responses.append(event.status.message)
        
        print(f"Received {len(responses)} response messages.")
        for resp in responses:
            for part in resp.parts:
                if isinstance(part.root, TextPart):
                    print(f"Response: {part.root.text}")
                    if "S6530532" in part.root.text:
                        print("SUCCESS: Found correct MRN!")
                    elif "Brian Buchanan" in part.root.text:
                         print("PARTIAL SUCCESS: Mentioned patient name.")

if __name__ == "__main__":
    asyncio.run(test_integration())
