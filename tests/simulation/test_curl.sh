#!/bin/bash
set -e

AGENT_URL=${AGENT_URL:-http://localhost:9009}
echo "Testing Agent at $AGENT_URL..."

# 1. Get Agent Card
echo "1. Checking Agent Card..."
curl -s -f "$AGENT_URL/.well-known/agent-card.json" | jq . || { echo "Failed to get agent card"; exit 1; }
echo -e "\nAgent Card OK.\n"

# 2. Send Message
echo "2. Sending 'Hello' message via JSON-RPC..."
# Generate a random ID
MSG_ID="curl-test-$(date +%s)"

PAYLOAD=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"text": "Hello, this is a curl test."}],
      "messageId": "$MSG_ID"
    }
  },
  "id": 1
}
EOF
)

RESPONSE=$(curl -s -X POST "$AGENT_URL" -H "Content-Type: application/json" -d "$PAYLOAD")

if echo "$RESPONSE" | grep -q "result"; then
  echo "Response received:"
  echo "$RESPONSE" | jq .
  echo "Curl Test PASSED."
else
  echo "Error or unexpected response:"
  echo "$RESPONSE"
  exit 1
fi
