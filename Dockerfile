# Multi-stage build for smaller image
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy only package sources (not root pyproject.toml to avoid workspace editable overrides)
COPY packages ./packages
COPY README.md LICENSE ./

# Build wheels and install into isolated venv
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install packages/core packages/api packages/sdk

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    espeak-ng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 vocal && \
    mkdir -p /home/vocal/.cache/vocal && \
    chown -R vocal:vocal /home/vocal

USER vocal
WORKDIR /home/vocal

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start API server
CMD ["uvicorn", "vocal_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
