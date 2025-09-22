# Multi-stage build for slim runtime image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_HOME=/opt/poetry \
    POETRY_VERSION=1.7.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

# Copy dependency files
WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-dev --no-root

# Copy application code
COPY ghostctl/ ./ghostctl/

# Build the package
RUN poetry build

# Runtime stage
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 ghostctl && \
    mkdir -p /home/ghostctl/.config

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy built package from builder
WORKDIR /app
COPY --from=builder /app/dist/*.whl /tmp/

# Install the package
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl

# Set up volumes for configuration
VOLUME ["/home/ghostctl/.config"]

# Switch to non-root user
USER ghostctl
WORKDIR /home/ghostctl

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ghostctl --version || exit 1

# Default command
ENTRYPOINT ["ghostctl"]
CMD ["--help"]