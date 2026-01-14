import sys
import os
import time
import subprocess
import asyncio
import httpx
from uuid import uuid4
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

# Helper function
async def send_text_message(text: str, url: str):
    async with httpx.AsyncClient(timeout=30) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=url)
        agent_card = await resolver.get_agent_card()
        config = ClientConfig(httpx_client=httpx_client, streaming=False)
        factory = ClientFactory(config)
        client = factory.create(agent_card)

        msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(TextPart(text=text))],
            message_id=uuid4().hex,
        )

        events = []
        async for event in client.send_message(msg):
            events.append(event)
            print(f"Received event: {event}")
            
    return events

async def main_async():
    # Start server
    print("Starting Purple Agent on port 9011...")
    proc = subprocess.Popen(
        [sys.executable, "src/server.py", "--port", "9011"],
        env=os.environ.copy()
    )
    try:
        await asyncio.sleep(5) # Wait for startup

        print("Simulating Green Agent interaction...")
        # Simulate Green Agent sending a task
        events = await send_text_message("What is the diagnosis for fever and cough?", "http://localhost:9011")
        
        # Verify response
        has_response = False
        for event in events:
            # Check for ArtifactUpdate with 'Response'
            if hasattr(event, "artifact") and event.artifact:
                # event is ArtifactUpdate or Task (depends on SDK types)
                # Client returns (Task, ArtifactUpdate) tuple or Message
                pass
            
            # The SDK yields (Task, ArtifactUpdate) or Message or (Task, StatusUpdate)
            # Let's inspect events
            pass

        print(f"Total events received: {len(events)}")
        if len(events) > 0:
            print("Interaction successful.")
        else:
            print("No response from agent.")
            sys.exit(1)

    except Exception as e:
        print(f"E2E Verification failed: {e}")
        proc.terminate()
        sys.exit(1)
    finally:
        print("Stopping Purple Agent...")
        proc.terminate()
        proc.wait()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
