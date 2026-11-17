FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY config ./config
COPY src ./src

RUN uv sync --no-dev \
    && uv run playwright install chromium --with-deps

CMD ["uv", "run", "phone-scraper", "scrape", "schedule"]
