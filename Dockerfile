FROM ghcr.io/astral-sh/uv:python3.13-bookworm

# Create a non-root user with an explicit UID
RUN adduser --disabled-password --gecos '' --uid 1000 agent

USER agent
WORKDIR /home/agent

# Copy dependency files first
COPY --chown=agent:agent pyproject.toml uv.lock README.md ./

# Install dependencies
RUN --mount=type=cache,target=/home/agent/.cache/uv,uid=1000 \
    uv sync --frozen --no-install-project

# Copy source code
COPY --chown=agent:agent src src
COPY --chown=agent:agent med_data med_data

# Install the project itself
RUN --mount=type=cache,target=/home/agent/.cache/uv,uid=1000 \
    uv sync --frozen

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/home/agent/.venv/bin:$PATH"

ENTRYPOINT ["uv", "run", "src/server.py"]
CMD ["--host", "0.0.0.0"]
EXPOSE 9010