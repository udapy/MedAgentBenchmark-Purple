#!/bin/bash
set -e

NETWORK_NAME="medagentbenchmark-green_medagent-network"

# Check if network exists
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    echo "Creating network $NETWORK_NAME..."
    docker network create "$NETWORK_NAME"
else
    echo "Network $NETWORK_NAME already exists."
fi

# Build image
echo "Building Purple Agent Docker image..."
docker build -t purple-agent .

# Run container
echo "Running Purple Agent container..."
# Using the .env file if it exists
ENV_ARGS=""
if [ -f .env ]; then
    ENV_ARGS="--env-file .env"
fi

# Stop/Remove existing containers matching the name
CONTAINERS=$(docker ps -a -q -f name=purple-agent)
if [ -n "$CONTAINERS" ]; then
    echo "Removing existing containers: $CONTAINERS"
    docker rm -f $CONTAINERS
fi


docker run -d \
    --name purple-agent \
    --network "$NETWORK_NAME" \
    -p 9010:9009 \
    $ENV_ARGS \
    purple-agent \
    --host 0.0.0.0 --card-url http://purple-agent:9009

echo "Purple Agent is running on port 9010 (mapped to 9009 inside container)."
