FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml README.md ./

RUN uv pip install --system .

COPY . .

EXPOSE 8001

CMD ["uvicorn", "src.api.rest.app:app", "--host", "0.0.0.0", "--port", "8001"]