# Development Dockerfile with hot reloading
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download tiktoken encoding so it works offline
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

# Source code will be mounted as volume
# CMD is for development with hot reload (uvicorn --reload)
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]
