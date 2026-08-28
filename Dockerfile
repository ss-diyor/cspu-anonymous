FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system bot && adduser --system --ingroup bot bot

COPY pyproject.toml README.md ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN python -m pip install --upgrade pip==26.2.1 && python -m pip install .

USER bot

EXPOSE 8000
CMD ["python", "-m", "app.start"]
