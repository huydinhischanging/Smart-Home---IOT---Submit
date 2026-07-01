# =============================================================
# Dockerfile — IOT Smart Home for Elderly (Backend)
# Build:  docker build -t alfred-backend .
# Run:    docker run --env-file .env -p 5000:5000 alfred-backend
# =============================================================

FROM python:3.11-slim

# ── System dependencies ────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libmariadb-dev-compat \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ──────────────────────────────────────
WORKDIR /app

# ── Python dependencies ────────────────────────────────────
# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ─────────────────────────────────────
COPY . .

# ── Non-root user (security best practice) ────────────────
RUN addgroup --system alfred && adduser --system --ingroup alfred alfred
RUN chown -R alfred:alfred /app
USER alfred

# ── Runtime configuration ─────────────────────────────────
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Port exposed by Gunicorn
EXPOSE 5000

# ── Healthcheck ───────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# ── Entrypoint ────────────────────────────────────────────
# Gunicorn + eventlet worker for Socket.IO compatibility
# DB must be initialized separately: docker exec <container> python init_db.py
CMD ["gunicorn", \
     "--worker-class", "eventlet", \
     "--workers", "1", \
     "--bind", "0.0.0.0:5000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:application"]
