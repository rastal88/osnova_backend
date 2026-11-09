# Osnova

[![CI](https://github.com/rastal88/osnova_backend/actions/workflows/ci.yml/badge.svg)](https://github.com/rastal88/osnova_backend/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**A modular full-stack template for web applications on Python (FastAPI) and React.**

Osnova gives a new project a ready architecture and the usual building blocks: languages,
forms, error handling, logging, Docker, CI. Optional capabilities (users, admin, files,
background tasks) are switched on by configuration.

> **Main idea:** start small and grow without rewriting. A project started as `minimal`
> can move to `standard` and `scalable` by changing configuration and infrastructure,
> not the architecture.

Two independent repositories that talk only through the API:

| Repository | Purpose | Stack |
|---|---|---|
| **osnova_backend** (this one) | API, business logic, data | Python · FastAPI · SQLAlchemy · PostgreSQL |
| [**osnova_frontend**](https://github.com/rastal88/osnova_frontend) | Web interface (SPA) | React · TypeScript · Vite |

Status: the `minimal` profile is ready; `standard` is in progress. See [ROADMAP.md](ROADMAP.md).

---

## Contents

- [Principles](#principles)
- [Profiles](#profiles)
- [Capabilities](#capabilities)
- [Stack](#stack)
- [Project layout](#project-layout)
- [Quick start](#quick-start)
- [Docker](#docker)
- [Configuration](#configuration)
- [API](#api)
- [Development](#development)

---

## Principles

- **Modular monolith.** One application; each optional capability is a module in its own
  folder, loaded only when enabled. Microservices are not required.
- **Configuration over code.** Capabilities, languages and infrastructure are chosen in `.env`.
- **The backend is the source of truth.** The frontend builds its routes and UI from
  `GET /api/v1/bootstrap`.
- **Pay only for what you use.** A disabled module is not imported, and its dependencies
  (`requirements/<module>.txt`) need not be installed.
- **Production-ready from the start.** Docker images, health checks, request ids, CI.

---

## Profiles

The same code runs in three profiles; moving between them changes configuration and the
services around the app.

### Minimal

```
Frontend ──▶ FastAPI
```

Sites, landing pages, small services and simple APIs. No database, Redis or workers; only
`requirements/base.txt` is installed. Included: languages (`en`, `ru`), forms with
validation, rate limit and honeypot, unified errors, request ids, OpenAPI for the frontend.

### Standard

```
                 ┌───── PostgreSQL
Frontend ──▶ FastAPI
                 ├───── Redis
                 └───── Celery workers
```

The main profile for full applications: users and roles, admin, files, background tasks.
The goal is a working *foundation* for each tool, not a complete integration.

### Scalable

```
                Frontend (nginx)
                 /          \
            FastAPI        FastAPI    (replicas)
                 \          /
             PostgreSQL · Redis
```

`standard` with several backend replicas: the backend publishes no host port and the
frontend nginx spreads requests over the replicas through Docker DNS. A load balancer,
CDN and monitoring are not part of the template yet.

---

## Capabilities

Each capability is an environment flag. The backend collects them and sends them to the
frontend in `/bootstrap`:

```
.env flags                 app/core/capabilities.py     GET /api/v1/bootstrap      Frontend
AUTH_ENABLED          ──▶  Capabilities            ──▶  { application, profile, ──▶ routes + UI
ADMIN_ENABLED                                             i18n, features }
FILES_ENABLED
NOTIFICATIONS_ENABLED
BACKGROUND_TASKS_ENABLED
```

When a capability is off, the frontend does not create its routes or UI:

| Capability | Off: the frontend has no |
|---|---|
| `authentication` | `/login`, `/register`, protected routes (every page is public) |
| `admin` | `/admin` section and its menu items |
| `files` | upload / download components |
| `notifications` | notification centre (for now only the flag exists) |
| `background_tasks` | usually nothing visible |

Flags by profile:

| Flag | Minimal | Standard | Scalable |
|---|:---:|:---:|:---:|
| `AUTH_ENABLED` | ✕ | ✓ | ✓ |
| `ADMIN_ENABLED` | ✕ | ✓ | ✓ |
| `FILES_ENABLED` | ✕ | optional | optional |
| `NOTIFICATIONS_ENABLED` | ✕ | optional | optional |
| `BACKGROUND_TASKS_ENABLED` | ✕ | ✓ | ✓ |
| PostgreSQL / Redis | ✕ | ✓ | ✓ |
| Several backend replicas | ✕ | ✕ | ✓ |

A module that lacks what it needs stops the start with a clear message, e.g.
`AUTH_ENABLED=true` without `DATABASE_URL`.

---

## Stack

**Backend:** Python 3.13, FastAPI, Uvicorn, Pydantic v2 / pydantic-settings. Optional
modules: SQLAlchemy 2.0 (async) + asyncpg + Alembic, `fastapi-users` (JWT, cookies,
roles), Redis, Celery. Tools: ruff, pytest.

**Frontend** ([osnova_frontend](https://github.com/rastal88/osnova_frontend)): React 19,
TypeScript, Vite, Ant Design, Zustand, React Router, Axios, react-i18next. Tools: Biome,
Vitest.

**Infrastructure:** Docker Compose profiles `minimal` / `standard` / `scalable`, nginx for
the SPA and as the API proxy, GitHub Actions CI.

---

## Project layout

```
osnova_backend/
├── app/
│   ├── core/              # always loaded: bootstrap, health, capabilities, languages,
│   │                      # errors, forms, rate limit, request id, module registry
│   ├── modules/           # optional modules, one folder each
│   │   ├── db/            # SQLAlchemy (async) sessions       ← DATABASE_URL
│   │   ├── auth/          # fastapi-users, roles, User model  ← AUTH_ENABLED
│   │   ├── admin/         # admin area API (root, moderator)  ← ADMIN_ENABLED
│   │   ├── settings/      # settings stored in the database   ← ADMIN_ENABLED
│   │   ├── files/         # file upload / download            ← FILES_ENABLED
│   │   └── tasks/         # Celery app                        ← BACKGROUND_TASKS_ENABLED
│   ├── client/            # client area API (any signed-in user)
│   ├── forms.py           # the project's forms
│   ├── settings.py        # settings groups edited in the admin (site, languages)
│   ├── config.py          # settings (every value has a default)
│   └── __init__.py        # application factory
├── migrations/            # Alembic migrations
├── requirements/          # per module: base, db, auth, files, tasks, redis;
│                          # standard (all modules), dev (all + tools)
├── scripts/openapi.py     # writes openapi.json for the frontend
├── tests/
├── openapi.json           # API schema, committed (the frontend generates types from it)
├── Dockerfile             # backend image (ARG REQUIREMENTS=base|standard)
├── docker-compose.yml     # base compose, safe for minimal
├── docker-compose.datastores.yml  # adds PostgreSQL + Redis (standard / scalable)
├── Makefile               # all commands: make help
└── manage.py              # CLI: createroot
```

---

## Quick start

Requirements: Python 3.13; Node.js 24 for the frontend; PostgreSQL only for modules that
need a database.

```bash
git clone https://github.com/rastal88/osnova_backend.git
git clone https://github.com/rastal88/osnova_frontend.git   # next to it, for make dev-all
cd osnova_backend
make install              # venv + requirements/dev.txt (all modules + tools)
cp .env.example .env      # optional: an empty .env runs the minimal profile
make dev-all              # API + frontend dev server; Ctrl+C stops both
```

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000/api/v1`, docs at `http://localhost:8000/docs`

`make dev` starts only the API (host and port from `APP_HOST` / `APP_PORT`). For the
minimal profile alone `pip install -r requirements/base.txt` is enough.

### With a database and users

```bash
# .env: DATABASE_URL=postgresql+asyncpg://osnova:osnova@localhost:5432/osnova
#       AUTH_ENABLED=true, SECRET_KEY=<long random value>
alembic upgrade head          # one initial migration: migrations/versions/0001_initial_schema.py
python manage.py createroot   # first user with the root role
```

---

## Docker

Both repositories must sit side by side (`osnova_backend/`, `osnova_frontend/`); one
`.env` in the backend configures both.

```bash
cp .env.example .env
make up-minimal       # backend + frontend
make up-standard      # + PostgreSQL + Redis
make up-scalable      # standard with 3 backend replicas
make logs             # follow logs
make down             # stop (make down-volumes also deletes data)
```

Only the frontend is published: `http://localhost:8080` (`FRONTEND_PORT`). nginx proxies
`/api`, `/docs`, `/redoc` and `/openapi.json` to the backend, so there is one origin and
no CORS.

How it works:

- **Backend image:** `python:3.13-slim`, non-root, `uvicorn`, with a health check.
  `REQUIREMENTS=base` for minimal,
  `standard` with the datastore override. Port `8000` is exposed only inside the compose
  network, so replicas do not clash.
- **Datastores:** `postgres` and `redis` live in `docker-compose.datastores.yml` and run
  only for `standard` / `scalable`. Their addresses are set by compose; `localhost` values
  from `.env` are ignored. In `minimal` `DATABASE_URL` and `REDIS_URL` are forced empty.
- **Migrations:** with `RUN_MIGRATIONS=true` and a database the entrypoint runs
  `alembic upgrade head` before the app starts.
- **Health checks:** `GET /api/v1/health` for the backend; built-in ones for postgres and
  redis.
- **Standard:** set `APP_PROFILE=standard` and the flags you need in `.env`.
  `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` default to `osnova`.

---

## Configuration

All settings are in [`app/config.py`](app/config.py), each with a default; every one is
listed with comments in [`.env.example`](.env.example).

| Variable | Purpose |
|---|---|
| `APP_NAME`, `APP_VERSION`, `APP_PROFILE` | Name, version, profile (`minimal` / `standard` / `scalable`); a mismatch with the setup is logged as a warning at start |
| `APP_HOST`, `APP_PORT`, `DEBUG` | Local server address, debug mode |
| `AUTH_ENABLED`, `ADMIN_ENABLED`, `FILES_ENABLED`, `NOTIFICATIONS_ENABLED`, `BACKGROUND_TASKS_ENABLED` | Capabilities (see above) |
| `LANGUAGES`, `DEFAULT_LANGUAGE` | Enabled interface languages and the default (`app/core/languages.py`); initial values, changed later in Admin → Settings |
| `CORS_ORIGINS` | Allowed origins for local development, comma-separated |
| `FORMS_DELIVERY`, `FORMS_FILE` | Form delivery stub: `log`, or `file` (also JSON lines in `FORMS_FILE`) |
| `FORMS_RATE_LIMIT` | Submissions per client IP and form, e.g. `5/minute`; empty disables |
| `DATABASE_URL`, `DB_ECHO` | Database (turns on the `db` module), SQL logging |
| `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Token signing and lifetime (`SECRET_KEY` required with auth) |
| `AUTH_STRATEGY`, `COOKIE_SECURE` | `jwt` (default) or `redis` sessions; `Secure` cookie (HTTPS only) |
| `REDIS_URL` | Redis (for `AUTH_STRATEGY=redis`) |
| `SETTINGS_REFRESH_SECONDS` | How often each process reloads settings changed in the admin (default `30`) |
| `FILES_DIR`, `FILES_MAX_SIZE_MB` | Upload folder and size limit |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Celery (broker required with background tasks) |

Docker Compose only: `FRONTEND_PORT`, `SITE_URL` (public origin for canonical links,
link previews and `sitemap.xml`), `ANALYTICS_SCRIPT` (frontend analytics, loaded only after
cookie consent), `POSTGRES_*`, `RUN_MIGRATIONS`, `FORWARDED_ALLOW_IPS`.

---

## API

Prefix `/api/v1`. The full schema is in [`openapi.json`](openapi.json) and at `/docs`.
Errors share one format: `{ code, message, fields?, request_id? }`, with `message` in the
user's language (`Accept-Language`). Every response carries `X-Request-ID`.

| Method | Path | Purpose | When |
|---|---|---|---|
| GET | `/bootstrap` | Site name and contacts, version, profile, capabilities, languages | always |
| GET | `/health` | Liveness check | always |
| GET | `/forms/{name}` | Form description for the frontend (fields, labels, rules) | always |
| POST | `/forms/{name}` | Validate and deliver a form; `422` with per-field errors | always |
| — | `/auth/*` | Sign-up, sign-in, sign-out, password reset, verification, users | `AUTH_ENABLED` |
| GET | `/client/*` | Client area: any signed-in user (example: `/client/summary`) | `AUTH_ENABLED` |
| GET | `/admin/*` | Admin area: `root` and `moderator` (`/admin/overview`) | `ADMIN_ENABLED` |
| GET / PATCH | `/admin/users`, `/admin/users/{id}` | Users: search `q`, filters `role` / `status`, `sort`, `page` / `size`; block / unblock (moderator: ordinary users), change role (root) | `ADMIN_ENABLED` |
| GET / PUT | `/admin/settings`, `/admin/settings/{group}` | Settings groups with form descriptions; changes by `root` only | `ADMIN_ENABLED` |
| POST / GET | `/file_flow/upload`, `/file_flow/download/{name}` | Upload (signed-in users) and download | `FILES_ENABLED` |

---

## Development

| Command | Purpose |
|---|---|
| `make install` | venv + all modules and tools |
| `make dev` / `make dev-all` | API with reload / API + frontend dev server |
| `make test` | pytest (also checks that `openapi.json` is up to date) |
| `make lint` / `make format` | ruff check / fix |
| `make openapi` | write `openapi.json` after API changes, then `npm run generate:client` in the frontend |
| `make help` | all commands, including Docker ones |

- **Module = folder.** Each capability is a package `app/modules/<name>/` with
  `register(app)`. The registry `app/core/modules.py` imports it only when it is enabled
  and checks module dependencies (`requires`). The core never imports modules.
- **Remove a module:** delete its folder, its entry in `MODULES` and
  `requirements/<name>.txt`.
- **New endpoints for signed-in users:** add them to `client_router` (`app/client/routes.py`);
  admin ones to `admin_router` (`app/modules/admin/routes.py`). Both routers check access
  for every endpoint. A new domain: a package like `app/client/` and an entry in `MODULES`.
- **Add a capability:**
  1. A flag in `app/config.py` and `.env.example`.
  2. A package `app/modules/<name>/` with `register(app)` and an entry in `MODULES`.
  3. Dependencies in `requirements/<name>.txt`, included from `standard.txt`.
  4. A field in `Capabilities` (`app/core/capabilities.py`) and in `app/core/bootstrap.py`.
  5. Handle the flag in the frontend routes and UI.
- **Add a form:** a `Form` in `app/forms.py` and its texts in `app/core/locales/*.json`.
- **Add a setting the owner can change:** a field (with a default) in a group in
  `app/settings.py`, or a new `SettingsGroup` added to `GROUPS`; labels in the `settings`
  section of `app/core/locales/*.json`. No migration and no frontend code: the admin form
  is generated. Read it with `settings.get(SiteSettings).contact_email`. Values that need a
  restart, secrets and capability flags stay in `.env`.
- **Add a language:** `AVAILABLE_LANGUAGES` in `app/core/languages.py`, translations in
  `app/core/locales/`, then enable it in `LANGUAGES` or in Admin → Settings.
- **Migrations:** `alembic revision --autogenerate -m "<message>"`, then review the file
  (see [`migrations/README.md`](migrations/README.md)).

CI (GitHub Actions) runs ruff and the tests, checks that the migrations match the models on
PostgreSQL, starts the app with base requirements only, and builds the Docker image with base and with standard requirements.

---

## Roadmap, contributing, license

- Plan and status: [ROADMAP.md](ROADMAP.md); changes: [CHANGELOG.md](CHANGELOG.md).
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md); security: [SECURITY.md](SECURITY.md).
- License: [MIT](LICENSE).
