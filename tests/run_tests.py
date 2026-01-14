import sys
import os
import time
import subprocess
import httpx
import pytest

def main():
    # Define port for testing
    PORT = 9012
    AGENT_URL = f"http://localhost:{PORT}"
    
    # Start server
    print(f"Starting Purple Agent on port {PORT} for testing...")
    proc = subprocess.Popen(
        [sys.executable, "src/server.py", "--port", str(PORT)],
        env=os.environ.copy()
    )
    
    try:
        # Wait for startup
        print("Waiting for agent to start...")
        started = False
        for _ in range(10): # Try for 10 seconds
            try:
                httpx.get(f"{AGENT_URL}/.well-known/agent-card.json", timeout=1)
                started = True
                break
            except Exception:
                time.sleep(1)
        
        if not started:
            print("Failed to start agent for testing.")
            proc.terminate()
            sys.exit(1)

        print("Agent started. Running tests...")
        # Run pytest
        # We invoke pytest programmatically or via subprocess. Subprocess is safer for env isolation.
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_agent.py", "--agent-url", AGENT_URL],
            env=os.environ.copy()
        )
        
        if result.returncode != 0:
            print("Tests failed.")
            sys.exit(result.returncode)
        
        print("Tests passed.")

    except Exception as e:
        print(f"Test runner failed: {e}")
        sys.exit(1)
    finally:
        print("Stopping Purple Agent...")
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
