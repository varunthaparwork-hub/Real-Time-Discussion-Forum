# Notification Service Dockerfile
# FastAPI + async SQLAlchemy + asyncpg running on port 8003
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

# Create tables, then start the FastAPI server
CMD ["sh", "-c", "python -m app.create_tables && uvicorn app.main:app --host 0.0.0.0 --port 8003"]

EXPOSE 8003
