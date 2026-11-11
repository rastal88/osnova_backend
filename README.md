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

The main profile for full applications. The goal is a working *foundation* for each tool,
not a complete integration:

| Tool | What you get |
|---|---|
| Users | sign-up, sign-in (cookie, JWT or Redis sessions), email confirmation, password reset, Google |
| Areas | public, user (any signed-in user) and admin (the `admin.access` permission) with guards on both sides |
| Permissions | named actions (`leads.read`, `users.block`) checked by `require(...)`; roles are sets of them in the database, `root` has all |
| Admin | overview, users (search, block, role), leads, delivery channels, settings |
| Settings | typed groups edited in the admin (site, languages), no migration per field |
| Leads | form submissions stored, delivered to email / Telegram / webhook by a task |
| Files | private uploads, local disk or any S3-compatible bucket |
| Notifications | in-app bell, email as a second channel |
| Tasks | Celery worker; email and lead delivery retried while a service is down |

`.env` for standard (Docker sets the datastore addresses itself):

```bash
APP_PROFILE=standard
AUTH_ENABLED=true
ADMIN_ENABLED=true
SECRET_KEY=<long random value>
# optional
FILES_ENABLED=true
NOTIFICATIONS_ENABLED=true
BACKGROUND_TASKS_ENABLED=true
```

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

What changes with replicas — the template already handles the first group, the second is
what to watch:

| | Behaviour with several replicas |
|---|---|
| Sessions | JWT cookies are stateless; Redis sessions are shared. Either way a password change or reset and **Sign out everywhere** end every session of the user (`sessions_valid_after`); a single sign-out ends one JWT only when it expires, a Redis session at once |
| Settings | each replica reloads them every `SETTINGS_REFRESH_SECONDS` (30 s) |
| Background work | the Celery worker is a separate service; tasks go through Redis |
| Readiness | `GET /api/v1/ready` checks the database, Redis sessions and the task broker of the enabled modules: route traffic by it |
| **Migrations** | run them once (`make migrate`), not with `RUN_MIGRATIONS=true` on every replica |
| **Files** | `FILES_STORAGE=s3` for several machines; local files work only on one host (shared Docker volume) |
| **Form rate limit** | counted in each replica's memory: with N replicas a client may send up to N × `FORMS_RATE_LIMIT` (a Redis store is planned) |
| **Lead delivery without tasks** | runs in the replica that got the form; turn background tasks on for retries |

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
| `notifications` | in-app notifications (the bell); admins hear about new leads |
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
│   │   ├── entities/      # configurable entities (one table) ← ADMIN_ENABLED
│   │   ├── leads/         # submissions, delivery channels    ← ADMIN_ENABLED
│   │   ├── files/         # files: local or S3 storage        ← FILES_ENABLED
│   │   ├── notifications/ # in-app notifications, channels    ← NOTIFICATIONS_ENABLED
│   │   └── tasks/         # Celery app, email task, schedule  ← BACKGROUND_TASKS_ENABLED
│   ├── user/              # user area API (any signed-in user)
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
└── manage.py              # CLI: createroot, cleanup
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
- API: `http://localhost:8000/api/v1`, docs at `http://localhost:8000/docs` (with `DEBUG=true`)

`make dev` starts only the API (host and port from `APP_HOST` / `APP_PORT`). For the
minimal profile alone `pip install -r requirements/base.txt` is enough.

### With a database and users

```bash
# .env: DATABASE_URL=postgresql+asyncpg://osnova:osnova@localhost:5432/osnova
#       AUTH_ENABLED=true, SECRET_KEY=<long random value>
alembic upgrade head          # every migration in migrations/versions
python manage.py createroot   # first user with the root role
```

### Sign-in with Google

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → OAuth
   consent screen: create it (External; app name, support email).
2. Credentials → Create credentials → OAuth client ID → Web application. Authorized
   redirect URI: `<FRONTEND_URL>/oauth/google/callback`, e.g.
   `http://localhost:5173/oauth/google/callback` for development and
   `https://example.com/oauth/google/callback` for the site.
3. Put the client ID and secret into `.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
   and restart. `/bootstrap` then lists `"google"` in `auth_providers`, and the sign-in page
   shows the button.

No Google API has to be enabled: the email comes from the OpenID Connect userinfo
endpoint, and only an email Google has confirmed is accepted.

A new Google user gets an account with a confirmed email; an existing account with the
same email is linked. If that account never confirmed its email (anyone can sign up with
someone else's address), it is taken over: it gets a new random password, so the one typed
at sign-up stops working. Another provider: a client from `httpx_oauth.clients` in
`app/modules/auth/oauth.py` and its keys in `app/config.py`.

---

## Docker

Both repositories must sit side by side (`osnova_backend/`, `osnova_frontend/`); one
`.env` in the backend configures both.

```bash
cp .env.example .env
make up-minimal       # backend + frontend
make up-standard      # + PostgreSQL + Redis + Celery worker and beat
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
- **Datastores and worker:** `postgres`, `redis`, the Celery `worker` and `beat` (same image
  as the backend; `beat` sends scheduled tasks and always runs as one instance) live in `docker-compose.datastores.yml` and run only for `standard` / `scalable`. Their addresses are set by compose; `localhost` values
  from `.env` are ignored. In `minimal` `DATABASE_URL` and `REDIS_URL` are forced empty.
- **Migrations:** `make migrate` runs `alembic upgrade head` once in a one-off container;
  `make createroot` creates the first root user. With `RUN_MIGRATIONS=true` the entrypoint
  runs migrations on every start — fine for one backend, not for replicas.
- **Readiness:** `GET /api/v1/ready` answers 503 while the database (or Redis sessions) is
  unreachable; `GET /api/v1/health` only says the process runs.
- **Health checks:** `GET /api/v1/health` for the backend; `celery inspect ping` for the
  worker; built-in ones for postgres and redis.
- **Email links:** `FRONTEND_URL` is set from `SITE_URL` (or `http://localhost:8080`).
- **Standard:** set `APP_PROFILE=standard` and the flags you need in `.env`.
  `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` default to `osnova`.

---

## Configuration

All settings are in [`app/config.py`](app/config.py), each with a default; every one is
listed with comments in [`.env.example`](.env.example).

| Variable | Purpose |
|---|---|
| `APP_NAME`, `APP_VERSION`, `APP_PROFILE` | Name, version (defaults to the release of the code; leave it out of `.env`), profile (`minimal` / `standard` / `scalable`); a mismatch with the setup is logged as a warning at start |
| `APP_HOST`, `APP_PORT`, `DEBUG` | Local server address; `DEBUG=true` serves `/docs`, `/redoc` and `/openapi.json` (off in production) |
| `AUTH_ENABLED`, `ADMIN_ENABLED`, `FILES_ENABLED`, `NOTIFICATIONS_ENABLED`, `BACKGROUND_TASKS_ENABLED` | Capabilities (see above) |
| `LANGUAGES`, `DEFAULT_LANGUAGE` | Enabled interface languages and the default (`app/core/languages.py`); initial values, changed later in Admin → Settings |
| `CORS_ORIGINS` | Allowed origins for local development, comma-separated |
| `FORMS_DELIVERY`, `FORMS_FILE` | Form delivery stub: `log`, or `file` (also JSON lines in `FORMS_FILE`); with the admin, submissions are also stored as leads |
| `FORMS_RATE_LIMIT` | Submissions per client IP and form, e.g. `5/minute`; empty disables |
| `CAPTCHA_PROVIDER`, `CAPTCHA_SITE_KEY`, `CAPTCHA_SECRET_KEY` | Captcha on forms and sign-up: empty provider is off, `turnstile` is Cloudflare Turnstile with its two keys |
| `DATABASE_URL`, `DB_ECHO` | Database (turns on the `db` module), SQL logging |
| `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Token signing and lifetime (`SECRET_KEY` required with auth: at least 32 characters, not the example value, or the app does not start) |
| `AUTH_RATE_LIMIT` | Requests per client IP to each of sign-in, sign-up, password reset and email confirmation, e.g. `10/minute`; empty disables |
| `AUTH_STRATEGY`, `COOKIE_SECURE` | `jwt` (default) or `redis` sessions; `Secure` cookie (HTTPS only) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Sign-in with Google (both set turns it on) |
| `REDIS_URL` | Redis (for `AUTH_STRATEGY=redis`) |
| `NOTIFICATIONS_CHANNELS` | Where notifications go besides the bell: `in_app` (default), `in_app,email` |
| `SETTINGS_REFRESH_SECONDS` | How often each process reloads settings changed in the admin (default `30`) |
| `FILES_STORAGE`, `FILES_DIR`, `FILES_MAX_SIZE_MB`, `FILES_ALLOWED_TYPES` | `local` (folder `FILES_DIR`) or `s3`; size limit; allowed MIME types or prefixes (empty: any) |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_LINK_SECONDS` | S3-compatible bucket for `FILES_STORAGE=s3`; lifetime of download links |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Celery (broker required with background tasks) |
| `NOTIFICATIONS_KEEP_DAYS`, `UNVERIFIED_ACCOUNT_DAYS` | Nightly cleanup: days to keep read notifications (90) and never confirmed accounts (0 = keep) |
| `FRONTEND_URL` | Public address of the frontend, for links in emails |
| `MAIL_BACKEND`, `MAIL_FROM` | `console` (log, default) or `smtp`; sender address |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SECURITY`, `SMTP_TIMEOUT` | SMTP server; `starttls` (default), `ssl` or `none` |

Docker Compose only: `FRONTEND_PORT`, `SITE_URL` (public origin for canonical links,
link previews and `sitemap.xml`), `ANALYTICS_SCRIPT` (frontend analytics, loaded only after
cookie consent), `POSTGRES_*`, `RUN_MIGRATIONS`, `FORWARDED_ALLOW_IPS`.

---

## API

Prefix `/api/v1`. The full schema is in [`openapi.json`](openapi.json) and at `/docs` (`DEBUG=true`).
Errors share one format: `{ code, message, fields?, request_id? }`, with `message` in the
user's language (`Accept-Language`). Every response carries `X-Request-ID`.

| Method | Path | Purpose | When |
|---|---|---|---|
| GET | `/bootstrap` | Site name and contacts, version, profile, capabilities, languages, sign-in providers | always |
| GET | `/health` | Liveness: the process runs | always |
| GET | `/ready` | Readiness: the database, Redis sessions and the task broker of the enabled modules answer; 503 otherwise | always |
| GET | `/forms/{name}` | Form description for the frontend (fields, labels, rules) | always |
| POST | `/forms/{name}` | Validate and deliver a form; `422` with per-field errors | always |
| — | `/auth/*` | Sign-up, sign-in, sign-out, password reset, verification, users; `PATCH /auth/users/me` changes only the name | `AUTH_ENABLED` |
| — | `/auth/me/*` | The user's own account, each with the current password: `POST password` (other sessions end), `POST email` (confirmed again, the old address is told), `POST sign-out-everywhere`, `DELETE` (with files and notifications; root cannot) | `AUTH_ENABLED` |
| GET | `/auth/google/authorize`, `/auth/google/callback` | Sign-in with Google (`authorization_url`, then the callback signs in) | `GOOGLE_CLIENT_*` set |
| GET | `/user/*` | User area: any signed-in user (example: `/user/summary`) | `AUTH_ENABLED` |
| GET | `/admin/*` | Admin area: the `admin.access` permission (`/admin/overview`); its sections ask for their own permissions, see [Permissions](#permissions) | `ADMIN_ENABLED` |
| GET / PATCH / DELETE | `/admin/leads`, `/admin/leads/{id}`, `/admin/leads/forms` | Form submissions: search `q` in the data, filters `form` / `status`, `sort`, pages; mark `new` / `done`; delete | `ADMIN_ENABLED` |
| GET / POST / PUT / DELETE | `/admin/entities`, `/admin/entities/{id}`, `/admin/entities/types` | Configurable entities (e.g. lead channels) with form descriptions; secrets masked; changes need `entities.manage` | `ADMIN_ENABLED` |
| POST | `/admin/leads/channels/{id}/test` | Send a test message through a channel (`entities.manage`) | `ADMIN_ENABLED` |
| GET | `/admin/users/export`, `/admin/leads/export` | CSV file of everything the list shows with the same `q`, filters and `sort` (no pages); `delimiter=comma` / `semicolon`, by the request language when not given | `ADMIN_ENABLED` |
| GET / PATCH | `/admin/users`, `/admin/users/{id}` | Users: search `q`, filters `role` / `status`, `sort`, `page` / `size`; block / unblock (`users.block`), change role (`users.roles`, also needed to block someone with a role other than `user`) | `ADMIN_ENABLED` |
| GET / PUT | `/admin/settings`, `/admin/settings/{group}` | Settings groups with form descriptions; changes need `settings.manage` | `ADMIN_ENABLED` |
| GET / POST / DELETE | `/notifications`, `/notifications/unread`, `/notifications/read`, `/notifications/{id}/read`, `/notifications/{id}` | The user's notifications in the request language, unread count, mark read, delete | `NOTIFICATIONS_ENABLED` |
| POST / GET / DELETE | `/files`, `/files/{id}` | The user's files: upload (size / type limits), list with search, download (owner and `files.manage`; S3: redirect to a short-lived link), delete | `FILES_ENABLED` |

---

### Permissions

A permission is a named action. A module declares its own and asks for them with one
dependency; `GET /auth/users/me` lists the user's `permissions` for the frontend.

```python
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import ADMIN_ACCESS, permission

ORDERS_READ = permission("orders.read")
router = APIRouter(dependencies=[Depends(require(ADMIN_ACCESS, ORDERS_READ))])
```

A role is a row of the `roles` table with a set of permissions; a user has one role
(`users.role`). Three roles come with the template: `root` always has every permission,
`user` has none and is given at sign-up, `moderator` starts with the ones below.

| Permission | Allows | `moderator` |
|---|---|---|
| `admin.access` | open the admin area | yes |
| `users.read`, `users.export`, `users.block` | the users list, its CSV, block / unblock | yes |
| `users.roles` | change a role; block users who have a role other than `user` | |
| `leads.read`, `leads.manage`, `leads.export` | leads: see, mark and delete, CSV | yes |
| `entities.manage` | create and change entities (lead channels), send a test message | |
| `settings.manage` | change the settings | |
| `files.manage` | open and delete files of other users | yes |

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
- **New endpoints for signed-in users:** add them to `user_router` (`app/user/routes.py`);
  admin ones to `admin_router` (`app/modules/admin/routes.py`). Both routers check access
  for every endpoint. A new domain: a package like `app/user/` and an entry in `MODULES`.
- **Add a capability:**
  1. A flag in `app/config.py` and `.env.example`.
  2. A package `app/modules/<name>/` with `register(app)` and an entry in `MODULES`.
  3. Dependencies in `requirements/<name>.txt`, included from `standard.txt`.
  4. A field in `Capabilities` (`app/core/capabilities.py`) and in `app/core/bootstrap.py`.
  5. Handle the flag in the frontend routes and UI.
- **Send an email:** texts in the `mail` section of `app/core/locales/*.json`
  (`<name>.subject`, `<name>.body`), then
  `await send_mail(render_mail("<name>", to, **params))` (`app/core/mail`). With background
  tasks on, it goes through the queue and the worker retries while the mail server is down.
  Every message has the text and an HTML version in one layout
  (`app/core/mail/layout.html`, `button.html`: site name, heading, a button for `link`;
  colours are edited there). The console backend prints the text.
  After sign-up the user gets a confirmation link; `forgot-password` sends a reset link —
  both open frontend pages (`/verify-email`, `/reset-password`).
- **Notify users:** `await notify(session, users, "<kind>", params, link="/path")`
  (`app/modules/notifications/service.py`) with texts `notifications.<kind>.title` / `.body`
  in the locales; they are translated when read. Example: new leads in
  `app/modules/leads/service.py`. Another channel (Telegram...): a function in
  `app/modules/notifications/channels.py`, listed in `NOTIFICATIONS_CHANNELS`.
- **Add a configurable entity:** a Pydantic model with `@entity_type` (`app/core/entities.py`;
  `type`, `group`, fields with defaults) and labels in the `entities` section of the
  locales. It is stored in the shared `entities` table and edited in the admin without a
  migration or frontend code. Example: the lead channels in `app/modules/leads/channels.py`.
- **Add a background task:** a function with `@celery_app.task` in
  `app/modules/tasks/tasks.py`, called with `.delay(...)`.
- **Run a task on a schedule:** an entry in `beat_schedule`
  (`app/modules/tasks/celery_app.py`) with the task name and a `crontab` (UTC).
- **Export a table to CSV:** `csv_response("<name>", header, rows)` (`app/core/csv_export.py`)
  streams a file a spreadsheet opens: UTF-8 with a BOM, UTC dates, `;` between columns for
  languages where Excel expects it, cells that would run as formulas made text. `rows` is
  an async iterator; read it with `session.stream_scalars(...)` in a session of its own.
  Examples: `export_users` (`app/modules/admin/users.py`), `export_leads`
  (`app/modules/leads/routes.py`).
- **Clean old data:** every night at 03:30 UTC the `maintenance.cleanup` task removes read
  notifications older than `NOTIFICATIONS_KEEP_DAYS` (90) and, when
  `UNVERIFIED_ACCOUNT_DAYS` is set, accounts that never confirmed the email and never
  signed in. Without Celery run `python manage.py cleanup` from cron (`make cleanup` in
  Docker). Another rule: `cleanup.py` in the module with `async def cleanup(session) -> int`
  and an entry in `JOBS` (`app/modules/db/cleanup.py`).
- **Add a form:** a `Form` in `app/forms.py` and its texts in `app/core/locales/*.json`.
- **Captcha (optional):** set `CAPTCHA_PROVIDER=turnstile` with `CAPTCHA_SITE_KEY` and
  `CAPTCHA_SECRET_KEY` (Cloudflare dashboard → Turnstile; test keys are in `.env.example`).
  `/bootstrap` then has `captcha: {provider, site_key}`, and `POST /forms/{name}` and
  `POST /auth/register` need the widget's token in the `X-Captcha-Token` header (400
  `captcha_failed` otherwise). The honeypot and rate limits stay. Root switches it off and on
  without a restart in Admin → Settings → Protection (the keys stay in `.env`; switching on
  without them is refused with a message). If Cloudflare cannot be reached, requests are let
  through with a warning in the log. Protect another endpoint with
  `Depends(require_captcha)`; another provider is a function in `PROVIDERS`
  (`app/core/captcha.py`).
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
