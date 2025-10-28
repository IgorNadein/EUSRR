# EUSRR Backend — Quickstart

## What’s inside
- Django 5.2, DRF, SimpleJWT
- Apps: employees, requests_app (HR requests), calendar_app, feed (news), communications (chat via Channels), bots (Telegram via aiogram), documents, search, hikcentral (read-only models to external DB)
- ASGI via Channels; Redis required for websockets

## Local run (SQLite, no websockets)
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp backend/.env backend/.env.local || true
# Edit backend/.env.local if needed (USE_SQLITE=True by default)
python backend/manage.py migrate
python backend/manage.py createsuperuser
python backend/manage.py runserver 0.0.0.0:9000
```
Open [http://127.0.0.1:9000/](http://127.0.0.1:9000/)

## Full stack with Docker (Postgres + Redis)
1. Put your secrets into `backend/.env` (use `.env.example` as a template). **Never commit real secrets.**
2. Ensure the `Dockerfile` uses `eusrr_backend.asgi` (or use the provided `Dockerfile.fixed`).
3. Launch:
```bash
docker compose up --build
```
The app will be available at [http://127.0.0.1:9000/](http://127.0.0.1:9000/)

## Useful commands
```bash
# Start Telegram bot
python backend/manage.py start_telegram_bot

# Run tests
pytest -q backend
```

## Notes
- Set `API_BASE_URL` to match where the app is served (default: [http://127.0.0.1:9000/api](http://127.0.0.1:9000/api)).
- For Channels websockets, ensure Redis is reachable at `${REDIS_HOST}:${REDIS_PORT}`.
- The `hikcentral` DB is configured as a secondary Postgres. Externalize its DSN via environment variables if you plan to use it.
