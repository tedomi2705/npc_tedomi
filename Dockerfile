# syntax=docker/dockerfile:1.23

FROM astral/uv:python3.13-trixie-slim AS build

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Omit development dependencies
ENV UV_NO_DEV=1

# Configure the Python directory so it is consistent
ENV UV_PYTHON_INSTALL_DIR=/python

# Only use the managed Python version
ENV UV_PYTHON_PREFERENCE=only-managed

# Install Python before the project for caching
RUN uv python install 3.14

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

FROM debian:trixie-slim AS runtime

WORKDIR /app

# Setup a non-root user
RUN groupadd --system --gid 999 nonroot \
    && useradd --system --gid 999 --uid 999 --create-home nonroot

# Install runtime dependencies
ENV DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,id=apt-cache-trixie,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lib-trixie,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates

# Copy the Python version
COPY --from=build /python /python

# Copy the application from the builder
COPY --from=build --chown=nonroot:nonroot /app /app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"HEALTH_PORT\", \"8080\")}/health', timeout=3).read()"]

# Use the non-root user to run our application
USER nonroot

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

CMD ["python", "main.py"]
