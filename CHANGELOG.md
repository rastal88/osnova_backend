# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Rate limits in Redis: `RATE_LIMIT_STORAGE=redis` (with `REDIS_URL`; Docker Compose sets
  it for standard and scalable) counts the form and sign-in hits in Redis, shared by every
  replica — one atomic Lua script, the same sliding window as in memory. When Redis cannot
  be reached the request is let through (fail-open): the process counts in memory, asks
  Redis again after 30 seconds and warns at most once a minute.
- JSON logs: `LOG_FORMAT=json` writes one object per line (time in UTC, level, logger,
  message, `request_id`, fields passed with `extra`, the traceback of an exception) for log
  collectors; `LOG_LEVEL` sets the level. Request lines carry `method`, `path`, `status`,
  `duration_ms`. uvicorn, the Celery worker and beat write through the same handler, so all
  lines share the format (Celery's own log setup is replaced; in Docker Compose the worker
  and beat start with `--quiet`, so the start banner, printed outside the logs, is gone).
- Docker Compose passes `CSP_EXTRA_ORIGINS` from `.env` to the frontend build (origins its
  Content Security Policy allows besides the analytics script, e.g. Google Analytics).

### Changed
- `APP_PROFILE=scalable` refuses `FILES_STORAGE=local` at start (each replica would keep
  its own files) and warns when rate limits count in each replica.
- `check_limit` is async (`await check_limit(limiter, key)`).

## [0.4.0] - 2026-11-11

Permissions and control: permissions as named actions, roles and groups edited in the
admin, an audit log, the user's language for emails, encrypted secrets, and the settings
the owner changes moved from `.env` to the admin.

### Added
- Permissions: named actions (`leads.read`, `users.block`, ...) declared by the modules with
  `permission(...)` and checked by one dependency, `require(...)`
  (`app/modules/auth/permissions.py`, README → Permissions). `UserRead` lists the user's
  `permissions`.
- Table `roles` (migration `0009`): a role is a set of permissions. `root` has every
  permission, `moderator` starts with what it could do before, `user` has none.

- Roles and groups in the admin API: `/admin/roles`, `/admin/groups` (changes need
  `roles.manage`) and `/admin/permissions` with texts in the request language. A group
  (migration `0010`) gives its roles to its users on top of their own role.
- `PATCH /admin/users/{id}` gives any role except root and `groups`; `GET /admin/users` has
  the `group` filter and returns each user's `groups`.
- Nobody hands out more than they have: roles, groups and users are changed only by someone
  who has every permission involved (`permission_not_allowed`).

- Audit log of admin actions (table `audit_log`, migration `0011`): who, when, from which IP,
  what and what changed (`{field: [before, after]}`), stored in the same transaction as the
  change. Recorded: block / unblock and role or groups of a user, roles and groups, settings,
  channels (entities), lead status and delete, CSV exports with their filters. Secret values
  are never stored, only that they changed; leads are named by the form, without the data of
  visitors. A record keeps the email when the account is deleted.
- `GET /admin/audit` (search, filters by action, who and days, sort, pages) and
  `GET /admin/audit/actions`, with the new permission `audit.read` (only `root` has it at
  first). Modules declare actions with `audit_action(...)` and record them with the `Audit`
  dependency (`app/modules/admin/audit.py`).
- `AUDIT_KEEP_DAYS` (365): the nightly cleanup removes older records (0 keeps them).
- The user's language (`users.language`, migration `0012`): set to the request language at
  sign-up (also with Google), changed with `PATCH /auth/users/me` (`language`, one of the
  enabled languages, else the field error `language_not_enabled`); in `UserRead` and in the
  admin users list. Old accounts have none and get the request language.
- `user_language(...)` (`app/core/i18n.py`): the user's own language while it is enabled, else
  the request language.
- Stored secrets are encrypted: `Secret` parameters of entities (Telegram bot token, webhook
  secret), `Secret` settings and the OAuth tokens (`access_token`, `refresh_token`). Fernet
  with a key derived from `SECRET_KEY` (HKDF), stored as `enc:...`; values stored before are
  read as they are. Migration `0013` encrypts what is already stored (downgrade decrypts).
  `app/modules/auth/encryption.py`: `encrypt` / `decrypt`, `encrypt_fields` /
  `decrypt_fields`, the `EncryptedText` column type. New dependency `cryptography` in
  `requirements/auth.txt` (not in the minimal profile).
- `OLD_SECRET_KEYS` and `python manage.py rotate-secrets`: change `SECRET_KEY` without losing
  the stored secrets.
- More settings in the admin (the `.env` values are the initial ones, a saved group wins):
  **Mail** (sending, sender, SMTP server, password stored encrypted), **Protection** (captcha
  provider and keys next to the switch, rate limits of forms and sign-in), **Data retention**
  (days for notifications, never confirmed accounts, audit log); with their modules
  **Files** (size, types) and **Notifications** (channels). A module's groups live in its
  `settings.py` (`GROUPS`).
- `POST /admin/settings/mail/test`: a test email to yourself with the saved mail settings,
  the mail server's error in the answer.
- Settings fields: `int` is described as `number` with `min_value` / `max_value`, and a field
  may have a hint (`help`, from `<group>.<field>.help`). Groups carry `editable`.
- `LimitFromSetting` and the `RateLimit` field type (`app/core/rate_limit.py`): a limit read at
  every request, so a change in the admin works without a restart.
- `SECRET_MASK`, `mask_secrets`, `keep_masked` in `app.core.settings`: settings `Secret`
  fields are masked in the admin API like entity secrets, and the mask sent back keeps the
  stored value.

### Changed
- `/admin/overview` counts users for every role of the project, not only the built-in ones.
- `users.role` is the slug of a role (a string with a foreign key) instead of a database
  enum; migration `0009` converts the stored values. In the API `role` is a string.
- Access checks ask for permissions instead of role lists. Nothing changes for `root`,
  `moderator` and `user`.
- The admin area opens with the `admin.access` permission (`areas` in `UserRead`).
- Captcha: the check waits up to 3 seconds for the provider instead of 5, so an outage on
  its side delays a form less (the request is still let through).

### Removed
- The `settings.manage` permission: one permission per settings group, `settings.<group>`
  (`settings.site`, `settings.mail`, ...). Migration `0014` gives roles that had it every
  group; groups with secrets (mail, protection) are shown only to those who may change them.
- `require_any_role` and `ADMIN_ROLES`: use `require("<permission>")`; `require_admin` stays.
- `users_with_roles` in the notifications service: use
  `app.modules.auth.dependencies.users_with_permission`.

### Fixed
- **Security:** the `user` role, given to every new account, could get staff permissions in
  Admin → Roles (e.g. `admin.access`), which would let everyone who signs up into the admin.
  It now refuses them (`403 role_user_staff`; only permissions declared with
  `everyone=True`, none in the template), and such permissions stored before do nothing.
  A person becomes staff with another role or a group, as before.
- Permissions a role keeps from a module that is switched off were not checked when the role
  was given or changed, so someone without them could hand them out for later; they count
  now (root has them all). `User.held_permissions`, `role_permissions(...)`;
  `GET /admin/permissions` tells which ones are for everyone (`everyone`).
- The Celery worker and `manage.py cleanup` use the settings saved in the admin (site name
  in emails, mail, retention): the worker loads them before a task, the cleanup before it runs.
- Email copies of notifications (e.g. a new lead) went out in the language of the request that
  caused them (the visitor's), now each recipient gets them in their own language.
- Account emails (confirm email, password reset, email change) and their links use the user's
  language instead of the request one.

## [0.3.0] - 2026-11-11

Account and everyday tools: account self-service, scheduled tasks with a cleanup, HTML
emails, CSV export, optional captcha.

### Added
- Account self-service, every change asks for the current password: `POST /auth/me/password`
  (other sessions end, this one gets a new cookie), `POST /auth/me/email` (confirmed again; the
  old address gets a notice), `POST /auth/me/sign-out-everywhere`, `DELETE /auth/me` (files and
  notifications removed; provider-only accounts confirm with their email; root cannot).
- User `name` (migration `0008`): sign-up, `PATCH /auth/users/me`, `UserRead`; the admin users
  list shows it and searches by it.
- Sessions that end for every device: tokens record when they were issued (JWT `iat`, next to
  the id in Redis) and are refused when older than the user's `sessions_valid_after`, set by
  a password change or reset and by sign out everywhere.
- `app.modules.auth.hooks.on_user_delete`: modules remove a deleted user's data (files,
  notifications).
- HTML emails: every message is sent as text and HTML in one layout
  (`app/core/mail/layout.html`: site name, heading, a button for the link); `render_html` for
  messages built by hand. Used by the account, notification and lead emails.
- Scheduled tasks: a `beat` service in Docker Compose and `beat_schedule` in the Celery app.
- Nightly cleanup (`maintenance.cleanup`, or `python manage.py cleanup` / `make cleanup`
  without Celery): read notifications older than `NOTIFICATIONS_KEEP_DAYS` (90) and, when
  `UNVERIFIED_ACCOUNT_DAYS` is set, accounts that never confirmed the email.
- CSV export: `GET /admin/users/export` and `GET /admin/leads/export` take the query of the
  lists (search, filters, sort) and stream every matching row; leads get a column per form
  field. `app/core/csv_export.py`: UTF-8 with a BOM, `;` or `,` by the request language
  (`delimiter` overrides), protection from spreadsheet formulas in the values.
- Optional captcha (`app/core/captcha.py`): `CAPTCHA_PROVIDER=turnstile` (Cloudflare Turnstile)
  with `CAPTCHA_SITE_KEY` / `CAPTCHA_SECRET_KEY` protects `POST /forms/{name}` and
  `POST /auth/register` (token in `X-Captcha-Token`, 400 `captcha_failed`); `/bootstrap`
  `captcha` tells the frontend. Off by default; root switches it in Admin → Settings →
  Protection, and switching on without the keys is refused with a message.

### Changed
- **Security:** `PATCH /auth/users/me` no longer changes the password or the email (it did
  without the current password, so a stolen session could take the account over); it takes
  only `name` and refuses other fields.
- VISION and ROADMAP: what the finished template (`v1.0.0`) is and the releases on the way —
  account and everyday tools, permissions, production and scalable, publication; what stays
  out of the template.

## [0.2.0] - 2026-11-10

The `standard` profile: users, areas and roles, admin, settings, leads with delivery
channels, files, notifications, background tasks, sign-in with Google.

### Added
- `/bootstrap` `api_docs`: whether `/docs` is served (`DEBUG`), so the frontend links to it only then.
- `GET /ready` also checks the task broker when background tasks are on.
- `app/version.py`: the release of the code, the default of `APP_VERSION`.
- `GET /admin/leads/stats?days=14`: leads total, by status and per day (UTC, days without leads
  included), for the admin overview.
- Rate limit on sign-in, sign-up, password reset and email confirmation:
  `AUTH_RATE_LIMIT` (default `10/minute` per client IP and endpoint), answered with 429 and
  `Retry-After`.
- `GET /api/v1/ready`: readiness — 200 when the dependencies of the enabled modules answer
  (database, Redis sessions), 503 with the failing one otherwise; checks have a 3 s timeout.
  Modules register checks with `app.core.readiness.add_check`.
- `make migrate` and `make createroot` for the Docker stack.
- README: what each profile gives and needs, and what changes with replicas (scalable).
- Sign-in with Google (fastapi-users OAuth + `httpx-oauth`, in `requirements/auth.txt`, about
  1.7 MB with `httpx`): on when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set.
  `GET /auth/google/authorize` gives the Google link; Google returns to
  `<FRONTEND_URL>/oauth/google/callback`, and that page calls `GET /auth/google/callback`,
  which signs in with the usual cookie. New users get a confirmed email; an account with the
  same email is linked. State and CSRF cookie are checked. Table `oauth_accounts`
  (migration `0007`).
- `/bootstrap` `auth_providers`: the configured sign-in providers, e.g. `["google"]`.
- Translated messages for OAuth errors.
- Notifications module (`NOTIFICATIONS_ENABLED`, migration `0006`): `notify(session, users,
  kind, params, link)` stores a notification per active user and sends it to the channels in
  `NOTIFICATIONS_CHANNELS` (`email` included; a channel is one function). Texts come from
  `notifications.<kind>.*` and are translated when read.
- `/api/v1/notifications`: the user's list (newest first, `unread_only`), `/unread` for the
  bell, mark one or all read, delete.
- Admins get a notification for every new lead, linking to Admin → Leads; a failure there
  never fails the form.
- Files: `/api/v1/files` — upload, the user's files with search and pages, download,
  delete; metadata in the `files` table (migration `0005`), contents in a storage chosen by
  `FILES_STORAGE`: `local` (`FILES_DIR`) or `s3` — any S3-compatible bucket through a small
  Signature V4 client on the standard library (no boto3), downloads redirect to a
  short-lived signed link (`S3_LINK_SECONDS`). `FILES_ALLOWED_TYPES` limits MIME types.
- Webhook channel: an invalid URL gets its own message (`url_invalid`).
- Configurable entities: an entity type is a Pydantic model registered with `@entity_type`
  (`app/core/entities.py`); all live in one table `entities` (migration `0004`). The
  `entities` module serves `/admin/entities` (list, create, update, delete; types with form
  descriptions at `/admin/entities/types`). Admins read, root changes; `Secret` fields
  (password inputs) come back as `********`, and sending that back keeps the stored value.
- Lead delivery channels (entities of the group `lead_channels`): email (`to`), Telegram
  (`bot_token`, `chat_id`) and webhook (`url`, optional `secret` → `X-Osnova-Signature:
  sha256=<HMAC>`). Each new lead goes to the enabled channels: via the Celery task
  `leads.deliver` with retries (1–16 minutes) when background tasks are on — in the web
  process if the queue is down — otherwise in the web process after the response. The text
  uses the lead's language and the form's labels. A refusal (4xx) is not retried.
- `Lead.deliveries`: the result per channel (status, error, time), in `/admin/leads`.
- `POST /admin/leads/channels/{id}/test` sends a test message and reports the error.
- Field types `Email` (required) and `Secret` (`password` input); `describe_field` for any
  model; `standalone_session()` for code running its own event loop.
- Leads: with the admin, every valid form submission is stored (module `leads`, table
  `leads`, migration `0003`) before the stub delivery; storing errors fail the request so
  the visitor can send again. Invalid and honeypot submissions are not stored.
- `GET /admin/leads` (search in the submitted data, filters `form` / `status`, sort, pages,
  `{items, total}`), `PATCH /admin/leads/{id}` (`new` / `done`), `DELETE /admin/leads/{id}`
  and `GET /admin/leads/forms` (form descriptions with labels for the admin table).
- Form receivers: `add_receiver` in `app/core/forms/delivery.py` lets a module handle every
  valid submission; `app_session(app)` in the db module opens a session outside a route.
- Email (`app/core/mail`, no new packages): `render_mail` builds a message from the `mail`
  translations, `send_mail` delivers it with `MAIL_BACKEND` — `console` (log, default) or
  `smtp` (`SMTP_*`, STARTTLS / SSL). Failures are logged, not raised.
- With background tasks on, emails go through the Celery task `mail.send` (retries with
  backoff while the server is down); sending fails fast when the broker is down.
- After sign-up the user gets a confirmation email; `forgot-password` sends a reset email.
  Links lead to `FRONTEND_URL/<language>/verify-email` and `/reset-password`.
- Docker Compose: the Celery `worker` service for standard / scalable, with a health check;
  `FRONTEND_URL` from `SITE_URL`.
- Admin users: `GET /admin/users` with search by email (`q`), filters `role` and `status`
  (`active`, `blocked`, comma-separated), `sort` (`email`, `role`, `date_created`,
  `last_login`; `-` for descending, newest first by default) and pages (`page`, `size` up
  to 100), returning `{items, total}`; `PATCH /admin/users/{id}` blocks / unblocks
  (`is_active`) and changes the role (`user` / `moderator`, root only). Nobody changes their
  own account or the root user; a moderator manages ordinary users only. A blocked user
  cannot sign in and loses access at the next request.
- Settings the owner changes at runtime: typed groups (`SettingsGroup`, `app/settings.py`)
  with defaults from `.env`, read with `settings.get(Group)`. With the admin the new
  `settings` module stores them in the database (table `settings`, one JSONB row per
  group, migration `0002`) and each process reloads them every `SETTINGS_REFRESH_SECONDS`.
- `GET /admin/settings`: every group with a form description (the `SchemaForm` format) and
  its values; `PUT /admin/settings/{group}` (root only) validates, stores and applies.
- Groups `site` (name, contact email and phone) and `languages` (enabled, default): the
  site name and contacts are in `/bootstrap` `application`; languages follow the settings.
- Form fields of type `multiselect`.
- Areas: `GET /auth/users/me` returns `areas` — `["admin", "user"]` for `root` and
  `moderator` when the admin module is on, otherwise `["user"]`; the first one is where
  the user lands after sign-in.
- `GET /admin/overview`: user counters for the admin dashboard.
- `APP_PROFILE` check: a warning at start when the profile does not match the setup
  (`minimal` with a database or modules, `standard` / `scalable` without `DATABASE_URL`).
- CI job that applies the migrations to PostgreSQL, runs `alembic check` and rolls them back.
- `VISION.md`: what Osnova is, the profiles and the stages of `standard`.

### Changed
- `APP_VERSION` is no longer in `.env.example`: a copied `.env` kept an old version.
- File names without backslashes in the quoted `Content-Disposition` name.
- The client area is now the user area: `areas` lists `"user"` instead of `"client"`
  (`Area.USER`), package `app/client` → `app/user` (`user_router`), `/client/summary` →
  `/user/summary` (`UserSummary`).
- Google sign-in reads the account from the OpenID Connect userinfo endpoint (scopes
  `openid email`) instead of the People API, which had to be enabled in Google Cloud
  separately; an email Google has not confirmed is refused.
- Google sign-in to an account whose email was never confirmed takes it over: a new random
  password replaces the one typed at sign-up (someone may have registered another person's
  address).
- The app does not start with auth on and a `SECRET_KEY` that is the example value or shorter
  than 32 characters.
- Without the tasks module, emails are sent in the background: sign-up, password reset and
  forms no longer wait for the mail server, and the reset response time no longer tells
  whether the email exists.
- With the leads module, the form log has only the form name, not the submitted data.
- `/docs`, `/redoc` and `/openapi.json` are served only with `DEBUG=true`.
- CORS headers are added to 500 responses too, so a frontend on another origin shows the
  server message instead of a network error.
- Sign-up no longer asks a provider-confirmed (OAuth) user to confirm the email again.
- Files are private: only the owner and admin roles download or delete them (someone
  else's file answers 404). Files are served as `attachment` with
  `application/octet-stream` and `nosniff`, except PNG / JPEG / GIF / WebP / AVIF images,
  so uploaded HTML or SVG never runs on the site's origin.
- `/file_flow/upload` and `/file_flow/download/{name}` are replaced by `/files`.
- Tests: the `client` fixture also runs on an in-memory SQLite database.
- The example task `tasks.send_notification` is replaced by `mail.send`; tasks are bound to
  `celery_app` (a `shared_task` called from a thread used the default Celery settings).
- The reset token is no longer written to the log in `DEBUG`: the console mail backend shows
  the whole email instead.
- `GET /admin/users` returns a page `{items, total}` instead of a plain list.
- API paths: `/user_flow/*` → `/client/*` (package `app/client`), `/admin_flow/*` →
  `/admin/*`; `/user_flow/main` is now `/client/summary`.
- Access is checked on the router: every endpoint of `client_router` needs a signed-in user,
  every endpoint of `admin_router` an admin role (`ADMIN_ROLES`). Unused `require_role` and
  `PERMISSIONS` removed.
- `/admin/users` has a response model and is sorted by email.
- The migration history is replaced by one initial migration `0001` with the same schema.
  An existing database created by the old history: run `alembic stamp --purge 0001` once.
- Autogenerated migrations use modern typing and render the user id as `sa.Uuid()`.
- `migrations/README.md` rewritten in English.

### Fixed
- An error from the OAuth provider (e.g. a refused token) answers 400 `oauth_provider_error`
  instead of 500.

### Removed
- The sample `hello` command of `manage.py`.

## [0.1.0] - 2026-11-07

First release: the `minimal` profile.

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

### Fixed
- Docker Compose passes `ANALYTICS_SCRIPT` from `.env` to the frontend build, so analytics
  and the cookie banner can be turned on in Docker.

### Removed
- Unused OAuth placeholder and `OAUTH2_*` settings (OAuth returns in the standard stage).

### Security
- Dependencies with known vulnerabilities updated: FastAPI 0.162 with Starlette 1.10 (now
  pinned), Uvicorn 0.54, fastapi-users 15.0.5, PyJWT 2.15.1 (now pinned), python-multipart
  0.0.33. `openapi.json` regenerated.
- `manage.py` no longer prints local variables in error tracebacks, which exposed the
  password given to `createroot`.
- Fixed path traversal in file download/upload.
- Password reset tokens are no longer logged outside `DEBUG`.

[Unreleased]: https://github.com/rastal88/osnova_backend/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/rastal88/osnova_backend/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/rastal88/osnova_backend/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/rastal88/osnova_backend/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/rastal88/osnova_backend/releases/tag/v0.1.0
