# MedAgentBenchmark Purple Agent

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

The **Purple Agent** is a medical AI agent designed to participate in the [MedAgentBenchmark](https://github.com/udapy/MedAgentBenchmark) ecosystem. It acts as a candidate model that interacts with the Green Agent (verifier/orchestrator).

## Features

- **A2A Protocol**: Fully compliant with the Agent-to-Agent protocol for standardized communication.
- **LLM Integration**: Supports OpenRouter and Nebius API for accessing medical LLMs (e.g., Gemini 2.0 Flash, DeepSeek).
- **Dockerized**: Production-ready Docker container with healthchecks and optimized caching.
- **CI/CD**: Automated testing and publishing to GitHub Container Registry (GHCR).

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (for local Python management)
- Docker & Docker Compose (for containerized execution)
- API Keys (OpenRouter or Nebius)

## Configuration

Create a `.env` file in the root directory (copy from `.env.example`):

```bash
cp .env.example .env
```

**Required Environment Variables:**

```env
# Choose one provider:
OPENROUTER_API_KEY=sk-or-...
NEBIUS_API_KEY=...

# Model Selection (defaults available):
OPENROUTER_MODEL_NAME=deepseek/deepseek-v3
NEBIUS_MODEL_NAME=deepseek-ai/DeepSeek-R1
MODEL_NAME=google/gemini-2.0-flash-exp:free
```

## Running Locally

1.  **Install dependencies:**

    ```bash
    make install
    ```

2.  **Run the agent:**
    ```bash
    make dev
    ```
    The agent will start on `http://localhost:9010` (mapped to port 9009 internally).

## Running with Docker

We provide a robust Docker setup for both development and production.

### Using Helper Script (Recommended)

This script handles network creation and container cleanup automatically.

```bash
./scripts/manage_docker.sh
```

### Using Docker Compose directly

```bash
docker compose up -d --build
```

The agent will be available at `http://localhost:9010`.

## Testing & Verification

The project includes a comprehensive suite of verification tools.

1.  **Unit Tests**:

    ```bash
    make test
    ```

2.  **Health Check**:

    ```bash
    make verify
    ```

3.  **End-to-End Simulation**:
    Simulates a full interaction flow locally.

    ```bash
    make verify-e2e
    ```

4.  **Curl Test**:
    Quick connectivity check using curl.
    ```bash
    make curl-test
    ```

## Deployment

The agent is automatically built and published to GHCR on push to main or valid tags.

- **Image**: `ghcr.io/<your-username>/medagentbench-purple-agent`
- **Tags**: `latest`, `v1.0.0` (semver)

### Manual Publish (from local)

Ensure you are logged in to GHCR (`docker login ghcr.io`).

```bash
make build
docker tag purple-agent ghcr.io/<user>/medagentbench-purple-agent:latest
docker push ghcr.io/<user>/medagentbench-purple-agent:latest
```

## Architecture

- **`src/server.py`**: A2A Server entrypoint and Agent Card definition.
- **`src/agent.py`**: Core agent logic and LLM interaction.
- **`Dockerfile`**: optimized Python image using `uv`.
- **`docker-compose.yml`**: Service definition connecting to the `medagentbenchmark-green_medagent-network`.

## Contributing

We welcome contributions! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch: `git checkout -b feature/your-feature`.
3.  Commit your changes: `git commit -m 'Add some feature'`.
4.  Push to the branch: `git push origin feature/your-feature`.
5.  Submit a pull request.

Please ensure your code passes all tests (`make check`) before submitting.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
