# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `make dev-all`: runs the API and the frontend dev server from `../osnova_frontend`
  (`FRONTEND=...` for another path, installs its packages on first run); Ctrl+C stops both.
- `openapi.json`: schema of the full API for the frontend client, written by `make openapi`;
  a test fails when it is out of date. Core endpoints (`/bootstrap`, `/health`, `/forms`)
  have response models, and error responses are documented as `ErrorResponse`. `pydantic`
  is pinned, since its version changes the schema.
- Request id: taken from `X-Request-ID` or generated, added to every log line and returned
  in the `X-Request-ID` header; 500 responses include it as `request_id`. One log line per
  request with method, path, status and duration.
- Forms: fields described once in `app/forms.py`; `GET /api/v1/forms/{name}` returns the
  translated description for the frontend, `POST /api/v1/forms/{name}` validates it with
  per-field errors and delivers it via a stub (`FORMS_DELIVERY=log|file`, `FORMS_FILE`).
  Example `contact` form with a required consent checkbox.
- Form protection: `FORMS_RATE_LIMIT` (default `5/minute` per client IP and form, 429 with
  `Retry-After`) and a honeypot field (`honeypot` in the form description) whose filled
  submissions are answered as usual but not delivered. Docker Compose sets
  `FORWARDED_ALLOW_IPS` so the client IP is taken from the frontend proxy.
- `AppError` accepts response `headers`.
- Interface languages: `LANGUAGES` (enabled, default `en,ru`) and `DEFAULT_LANGUAGE` (`en`),
  validated on startup and returned in `/bootstrap` as `i18n`.
- Backend messages in `app/core/locales/*.json`; the language comes from `Accept-Language`
  and is returned in `Content-Language`.
- Unified error format `{code, message}` (plus `fields` for validation errors) in the
  request language; `AppError` for raising errors by code.
- Capabilities (`*_ENABLED` flags) and `GET /api/v1/bootstrap`, `GET /api/v1/health`.
- Module registry: optional capabilities in `app/modules/*` are imported only when enabled,
  with dependency checks between modules.
- Per-module requirements in `requirements/`; the minimal image installs only `base.txt`.
- Docker Compose profiles `minimal` / `standard` / `scalable`, Makefile commands.
- `AUTH_STRATEGY`: JWT sessions by default, Redis optional.
- Files module: authenticated upload, server-generated names, `FILES_MAX_SIZE_MB` limit.
- CI: ruff, tests, minimal-install check, Docker builds. Open-source repository files.
- Docker Compose passes `SITE_URL`, `LANGUAGES`, `DEFAULT_LANGUAGE` and `APP_NAME` to the
  frontend build for prerendered SEO pages.

### Changed
- README rewritten in English and checked against the code: current status per profile,
  quick start with `make dev-all`, full settings and API tables; removed claims the code
  does not back (manual `uuid-ossp` step, multi-stage image, load balancer / CDN).
- Request logs no longer include the query string.
- Error responses no longer use `detail`; auth and files errors return stable codes.
- Every setting has a default; an empty `.env` runs the minimal profile.
- `user_flow` is registered only with auth and is open to every signed-in role.
- Database schema is created only by Alembic migrations.

### Removed
- Unused OAuth placeholder and `OAUTH2_*` settings (OAuth returns in the standard stage).

### Security
- Fixed path traversal in file download/upload.
- Password reset tokens are no longer logged outside `DEBUG`.
