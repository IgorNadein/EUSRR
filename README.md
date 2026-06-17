# EUSRR

EUSRR is an internal enterprise service portal built with Django, Django REST Framework, Next.js, PostgreSQL, Redis, Celery, WebSockets, LDAP integration, notifications, document workflows, procurement workflows, scheduling, and employee self-service modules.

The project demonstrates full-stack product development: backend architecture, REST APIs, role-based access, asynchronous tasks, realtime updates, frontend application structure, testing, deployment-oriented configuration, and production-style operational documentation.

## Core Modules

- Employee directory, profiles, departments, roles, and LDAP synchronization.
- Requests and approval workflows with status tracking and notifications.
- Procurement flows, approval routes, item handling, and delivery state tracking.
- Documents, files, comments, and internal collaboration features.
- Calendar and scheduling features with shared events.
- Realtime communications, WebSocket notifications, and chat-oriented workflows.
- LogStorm attendance integration for operational analytics.

## Tech Stack

- Backend: Python, Django, Django REST Framework, Channels, Celery, Redis, PostgreSQL.
- Frontend: Next.js, React, TypeScript, Tailwind CSS, Recharts, React Table.
- Integrations: LDAP, Web Push, Telegram/Synology-style notification adapters, LogStorm API.
- Testing: pytest for backend tests, Node test runner and ESLint for frontend checks.
- Deployment: Docker-oriented settings, environment-based configuration, Nginx-ready service layout.

## Repository Layout

```text
backend/   Django backend, APIs, Celery tasks, migrations, tests, docs
frontend/  Next.js frontend application
docs/      Architecture notes, implementation reports, guides, diagnostics
```

## Local Setup

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
python manage.py migrate
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open the frontend at `http://localhost:3000` and configure `NEXT_PUBLIC_BACKEND_URL` to point to the backend.

## Tests

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

## Security Notes

This public version is prepared as a portfolio snapshot. Environment files, local databases, media uploads, certificates, private keys, generated builds, and deployment-specific artifacts are excluded from version control.

All credentials must be supplied through environment variables. Example files contain placeholders only and must not be used as production secrets.

## Demo Data

The repository does not include production data. Any company-specific values should be replaced with local demo data before running the project outside its original environment.
