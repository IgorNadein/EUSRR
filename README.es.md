**Idioma:** [English](README.md) | [Русский](README.ru.md) | [Deutsch](README.de.md) | [Español](README.es.md)

# EUSRR

EUSRR es un portal interno de servicios empresariales construido con Django, Django REST Framework, Next.js, PostgreSQL, Redis, Celery, WebSockets, integración LDAP, notificaciones, flujos de documentos, flujos de compras, planificación y módulos de autoservicio para empleados.

El proyecto demuestra desarrollo full-stack de producto: arquitectura backend, REST APIs, control de acceso basado en roles, tareas asíncronas, actualizaciones en tiempo real, estructura frontend, pruebas, configuración orientada al despliegue y documentación operativa de estilo productivo.

## Módulos principales

- Directorio de empleados, perfiles, departamentos, roles y sincronización LDAP.
- Solicitudes y approval workflows con seguimiento de estado y notificaciones.
- Flujos de compras, approval routes, gestión de items y seguimiento de entrega.
- Documentos, archivos, comentarios y colaboración interna.
- Calendario y scheduling con eventos compartidos.
- Comunicaciones en tiempo real, WebSocket notifications y chat-oriented workflows.
- Integración con LogStorm para analítica operativa de asistencia.

## Stack técnico

- Backend: Python, Django, Django REST Framework, Channels, Celery, Redis, PostgreSQL.
- Frontend: Next.js, React, TypeScript, Tailwind CSS, Recharts, React Table.
- Integraciones: LDAP, Web Push, Telegram/Synology-style notification adapters, LogStorm API.
- Testing: pytest para backend tests, Node test runner y ESLint para frontend checks.
- Deployment: configuración orientada a Docker, environment-based configuration, Nginx-ready service layout.

## Estructura del repositorio

```text
backend/   Django backend, APIs, Celery tasks, migrations, tests, docs
frontend/  Next.js frontend application
docs/      Architecture notes, implementation reports, guides, diagnostics
```

## Configuración local

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

Abre el frontend en `http://localhost:3000` y configura `NEXT_PUBLIC_BACKEND_URL` para apuntar al backend.

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

Esta versión pública está preparada como portfolio snapshot. Los archivos de entorno, bases de datos locales, media uploads, certificados, private keys, builds generados y artefactos específicos de deployment están excluidos del control de versiones.

Todas las credenciales deben suministrarse mediante environment variables. Los archivos de ejemplo contienen solo placeholders y no deben utilizarse como production secrets.

## Demo Data

El repositorio no contiene production data. Cualquier valor especifico de empresa debe reemplazarse con datos demo locales antes de ejecutar el proyecto fuera de su entorno original.
