# Multi-stage Dockerfile for Food Cost Management System
# Updated for GitHub integration - Enhanced task summary calculations

# Builder stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim as production

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/app/.local

# Copy application code (as root before switching user)
COPY --chown=app:app app/ ./app/
COPY --chown=app:app templates/ ./templates/
COPY --chown=app:app static/ ./static/
COPY --chown=app:app data/ ./data/

# Ensure data directory has proper permissions
RUN chown -R app:app /app && chmod -R 755 /app

# Add local Python packages to PATH
ENV PATH=/home/app/.local/bin:$PATH

# Set environment variables
ENV PYTHONPATH=/app
ENV DATABASE_URL=sqlite:///app/data/food_cost.db

# Switch to non-root user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/login')" || exit 1

# Run the application
CMD ["gunicorn", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--access-logfile", "-", "--error-logfile", "-"]

# Development stage (optional)
FROM production as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir pytest pytest-asyncio httpx

USER app

# Override CMD for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]