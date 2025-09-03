# Multi‑app Django (ASGI) — EUSRR
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends     build-essential libpq-dev curl &&     rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app

# Use ASGI server because project uses Django Channels
EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "eusrr_backend.asgi:application"]
