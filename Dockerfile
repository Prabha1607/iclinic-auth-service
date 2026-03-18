FROM python:3.12-slim

WORKDIR /app

# Copy UV binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project metadata and install dependencies
COPY pyproject.toml README.md ./
RUN uv pip install --system .

# Copy all source code
COPY . .

# Expose a port (not strictly required by Cloud Run, but good practice)
EXPOSE 8080

# Start Uvicorn using the PORT env variable from Cloud Run, default to 8080 if not set
CMD ["sh", "-c", "uvicorn src.api.rest.app:app --host 0.0.0.0 --port ${PORT:-8080}"]