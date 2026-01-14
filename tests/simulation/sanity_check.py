import sys
import os
import time
import subprocess
import httpx

def main():
    # Start server
    print("Starting Purple Agent on port 9010...")
    proc = subprocess.Popen(
        [sys.executable, "src/server.py", "--port", "9010"],
        env=os.environ.copy()
    )
    time.sleep(5) # Wait for startup

    try:
        # Check agent card
        print("Checking agent card...")
        resp = httpx.get("http://localhost:9010/.well-known/agent-card.json")
        resp.raise_for_status()
        print("Agent card found:", resp.json())
        print("Purple agent is running as expected.")
        
    except Exception as e:
        print(f"Verification failed: {e}")
        proc.terminate()
        sys.exit(1)
    finally:
        print("Stopping Purple Agent...")
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
