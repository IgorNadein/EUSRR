**Sprache:** [English](README.md) | [Русский](README.ru.md) | [Deutsch](README.de.md) | [Español](README.es.md)

# EUSRR

EUSRR ist ein internes Enterprise-Service-Portal, entwickelt mit Django, Django REST Framework, Next.js, PostgreSQL, Redis, Celery, WebSockets, LDAP-Integration, Benachrichtigungen, Dokumenten-Workflows, Beschaffungsprozessen, Planung und Employee-Self-Service-Modulen.

Das Projekt zeigt Full-Stack-Produktentwicklung: Backend-Architektur, REST APIs, rollenbasierte Zugriffskontrolle, asynchrone Aufgaben, Echtzeit-Updates, Frontend-Struktur, Tests, deployment-orientierte Konfiguration und produktionsnahe Betriebsdokumentation.

## Kernmodule

- Mitarbeiterverzeichnis, Profile, Abteilungen, Rollen und LDAP-Synchronisierung.
- Anträge und Freigabe-Workflows mit Statusverfolgung und Benachrichtigungen.
- Beschaffungsprozesse, Freigaberouten, Artikelverwaltung und Lieferstatus.
- Dokumente, Dateien, Kommentare und interne Zusammenarbeit.
- Kalender- und Planungsfunktionen mit gemeinsamen Ereignissen.
- Echtzeitkommunikation, WebSocket-Benachrichtigungen und Chat-Workflows.
- LogStorm-Integration für operative Anwesenheitsanalysen.

## Tech Stack

- Backend: Python, Django, Django REST Framework, Channels, Celery, Redis, PostgreSQL.
- Frontend: Next.js, React, TypeScript, Tailwind CSS, Recharts, React Table.
- Integrationen: LDAP, Web Push, Telegram/Synology-style notification adapters, LogStorm API.
- Testing: pytest für Backend-Tests, Node test runner und ESLint für Frontend-Checks.
- Deployment: Docker-orientierte Einstellungen, umgebungsbasierte Konfiguration, Nginx-ready service layout.

## Repository-Struktur

```text
backend/   Django backend, APIs, Celery tasks, migrations, tests, docs
frontend/  Next.js frontend application
docs/      Architecture notes, implementation reports, guides, diagnostics
```

## Lokales Setup

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

Das Frontend ist unter `http://localhost:3000` erreichbar. `NEXT_PUBLIC_BACKEND_URL` muss auf das Backend zeigen.

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

Diese öffentliche Version ist als Portfolio-Snapshot vorbereitet. Environment-Dateien, lokale Datenbanken, Media Uploads, Zertifikate, private keys, generierte Builds und deployment-spezifische Artefakte sind aus der Versionskontrolle ausgeschlossen.

Alle Zugangsdaten müssen über Environment Variables bereitgestellt werden. Beispiel-Dateien enthalten nur Platzhalter und dürfen nicht als Production Secrets verwendet werden.

## Demo Data

Das Repository enthält keine Produktionsdaten. Unternehmensspezifische Werte sollten vor dem Betrieb außerhalb der ursprünglichen Umgebung durch lokale Demo-Daten ersetzt werden.
