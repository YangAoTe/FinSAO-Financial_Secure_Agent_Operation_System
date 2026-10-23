FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY banking_core ./banking_core
COPY agent_tools ./agent_tools
COPY shared ./shared
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "banking_core.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

