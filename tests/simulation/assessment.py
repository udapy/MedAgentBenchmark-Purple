import sys
import os
import json
import time
import httpx
import asyncio

# Configuration
GREEN_AGENT_URL = os.getenv("GREEN_AGENT_URL", "http://localhost:9009")
PURPLE_AGENT_URL = os.getenv("PURPLE_AGENT_URL", "http://localhost:9010")

async def main():
    print(f"--- AgentBeats Local Simulation ---")
    print(f"Green Agent: {GREEN_AGENT_URL}")
    print(f"Purple Agent: {PURPLE_AGENT_URL}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Check health of agents
        try:
            print("Checking Purple Agent...")
            resp = await client.get(f"{PURPLE_AGENT_URL}/.well-known/agent-card.json")
            resp.raise_for_status()
            print("Purple Agent is READY.")
        except Exception as e:
            print(f"Purple Agent NOT READY: {e}")
            sys.exit(1)

        try:
            print("Checking Green Agent...")
            # Assuming Green Agent has a similar endpoint or root
            resp = await client.post(GREEN_AGENT_URL, json={"jsonrpc": "2.0", "method": "health", "id": 1})
            # Note: Method might vary, but verify connectivity at least
            print("Green Agent is REACHABLE.")
        except Exception as e:
            print(f"Warning: Green Agent check failed or timed out: {e}")
            print("Proceeding anyway to attempt 'start_task'...")

        # 2. Trigger Assessment / Debug
        print("\n--- Debugging RPC Methods ---")
        
        # Try standard message/send first to verify A2A compliancy
        print("Attempting 'message/send' (Hello)...")
        msg_payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"text": "Hello, are you ready?"}],
                    "messageId": "msg-debug-001" 
                }
            },
            "id": "debug-1"
        }
        
        try:
             resp = await client.post(GREEN_AGENT_URL, json=msg_payload, timeout=10.0)
             print(f"message/send Status: {resp.status_code}")
             print(f"message/send Body: {resp.text}")
        except Exception as e:
             print(f"message/send failed: {e}")

        # Try variations of start_task
        methods_to_try = ["start_task", "control/start_task", "admin/start_task"]
        
        task_payload = {
            "jsonrpc": "2.0",
            "params": {
                "scenario": "local_scenario",
                "participants": [
                    {
                        "name": "purple-agent",
                        "url": "http://purple-agent:9009"
                    }
                ]
            },
            "id": "sim-retry"
        }
        
        # 3. Try sending JSON payload via message/send (Inferred from "Invalid JSON" error)
        print("\nAttempting 'message/send' with JSON payload...")
        
        # Construct the payload that we originally wanted to send to start_task
        # Error said: participants.purple-agent URL input should be a string ... input_value={'url': ...}
        # So participants should be a dict where key=ID and value=URL string.
        
        # NOTE: Since agents might be in separate stacks, we use host.docker.internal:9010 
        # to allow Green Agent (in container) to reach Purple Agent (on host port 9010).
        # We allow overriding this via env var (e.g. for LAN IP or internal docker alias).
        participant_url = os.getenv("PARTICIPANT_URL", "http://host.docker.internal:9010")
        
        print(f"Configuring Participant URL: {participant_url}")
        
        inner_payload = {
            "scenario": "local_scenario",
            "participants": {
                "purple-agent": participant_url
            }
        }
        
        msg_payload_json = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"text": json.dumps(inner_payload)}], # Send JSON string
                    "messageId": "msg-start-001" 
                }
            },
            "id": "sim-3"
        }
        
        try:
             resp = await client.post(GREEN_AGENT_URL, json=msg_payload_json, timeout=120.0)
             print(f"message/send (JSON) Status: {resp.status_code}")
             print(f"message/send (JSON) Body: {resp.text}")
             
             if resp.status_code == 200:
                 body = resp.json()
                 if "error" not in body:
                     # Check if result status is 'rejected' or 'completed'
                     res = body.get("result", {})
                     status = res.get("status", {}).get("state")
                     print(f"Result State: {status}")
                     if status != "rejected":
                         print("SUCCESS: JSON Payload accepted via message/send!")
                     else:
                         print("FAILED: Logic rejected the JSON payload (check format).")
        except Exception as e:
             print(f"message/send (JSON) failed: {e}")

        # 4. Introspection
        print("\n--- Introspection ---")
        try:
             resp = await client.get(f"{GREEN_AGENT_URL}/openapi.json", timeout=2.0)
             if resp.status_code == 200:
                 print("Found /openapi.json")
             else:
                 print(f"/openapi.json returned {resp.status_code}")
        except:
             pass

if __name__ == "__main__":
    asyncio.run(main())
