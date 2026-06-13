# GenSpark backend (Flask API) container.
# The React frontend (frontend/) is a static SPA — build it with `npm run build`
# and host it separately (e.g. Vercel/Netlify) or behind a static server.
FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV / Pillow used by the detection utilities.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching).
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the backend application.
COPY backend ./backend

ENV PORT=5000
EXPOSE 5000

# WSGI entry: backend/run.py exposes `app` (gunicorn run:app).
CMD ["sh", "-c", "gunicorn --chdir backend --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 120 run:app"]
