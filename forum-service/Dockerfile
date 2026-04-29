# Forum Service Dockerfile
# FastAPI + async SQLAlchemy + asyncpg running on port 8000
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Create tables, indexes, then start the FastAPI server
# The main.py lifespan also ensures the outbox table exists on startup
CMD ["sh", "-c", "python -m app.create_tables && python -m app.create_indexes && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

EXPOSE 8000
