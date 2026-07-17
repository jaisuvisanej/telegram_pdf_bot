# Use official slim Python runtime
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies (needed for compiling libraries if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config files
COPY src/ ./src/

# Create persistent storage directories
RUN mkdir -p uploads logs

# Expose port for FastAPI backend
EXPOSE 8000

# Default command (will be overridden in docker-compose for the bot service)
CMD ["python", "-m", "src.backend.main"]
