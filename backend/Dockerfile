# Use official Python runtime as a parent image
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Drop root privileges before running the app
RUN groupadd --system appuser && useradd --system --gid appuser --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Run the application
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
