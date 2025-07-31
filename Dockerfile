FROM python:3.12-slim AS builder

# Install build dependencies and python packages
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    rm -rf /root/.cache && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Set work directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system appuser && adduser --system --ingroup appuser appuser && \
    mkdir /tmp && chmod 1777 /tmp && chown -R appuser:appuser /app /tmp

# Copy project
COPY . .

# Switch to non-root user
USER appuser

# Define writable volume for /tmp
VOLUME /tmp

# Expose port and health check
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost/health || exit 1

# Run the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:80", "wsgi:app"]
