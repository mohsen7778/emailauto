# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# System deps only (no build tools in final image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps in a separate layer for cache efficiency
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# ── Runtime ────────────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# Non-root user for security
RUN useradd -m -u 10001 appuser
USER 10001

CMD ["python", "main.py"]
