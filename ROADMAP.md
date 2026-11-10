# Roadmap

Osnova was released in two steps, **minimal** (`v0.1.0`) and **standard** (`v0.2.0`, MVP);
the road to the finished template (`v1.0.0`) is in [VISION.md](VISION.md#8-road-to-v100-agreed-2026-11-10).

Legend: `[x]` done · `[~]` partly done · `[ ]` not started.
Items marked *(fe)* live in [osnova_frontend](https://github.com/rastal88/osnova_frontend),
*(be)* in this repository.

## Stage 0 — stabilisation and module layout

- [x] Capture in-progress work, fix the frontend build
- [x] Module = folder: optional capabilities are lazily loaded on both sides
- [x] Per-module dependencies (`requirements/*.txt`), minimal image without optional packages
- [x] Open-source repository layout (license, contributing, templates)

## Minimal profile (`v0.1.0`, released 2026-11-07)

### A. Layout and navigation *(fe)*
- [x] 1. App shell: header, collapsible side menu (left by default; right, top or off), footer, mobile menu
- [x] 2. Page frame: title, actions, shared states (loading, empty, error, forbidden)
- [x] 3. 404 and generic error pages
- [x] 4. Navigation from one config: active item, redirects
- [x] 5. Optional breadcrumbs

### B. Languages and SEO
- [x] 6. UI and content translations in files (react-i18next) *(fe)*
- [x] 7. Languages configured on the backend: available, enabled, default (`en`) — sent in `/bootstrap` *(be, fe)*
- [x] 8. Language switcher that remembers the choice *(fe)*
- [x] 9. Backend messages (errors, notifications) translated to the user's language *(be)*
- [x] 10. Language URLs (`/en`, `/ru`) and hreflang *(fe)*
- [x] 11. Per-page SEO: title, description, canonical *(fe)*
- [x] 12. Link previews for Telegram and social networks — via build-time prerender of `<head>` *(fe)*
- [x] 13. `sitemap.xml` and `robots.txt` *(fe)*

### C. Forms
- [x] 14. Form generated from a field description *(be, fe)* — description served by `GET /forms/{name}`
- [x] 15. Client and server validation with clear per-field errors *(fe, be)*
- [x] 16. Submit states (sending / success / error / retry) and a consent checkbox *(fe)*

### D. Look and data *(fe)*
- [x] 17. Light/dark theme and brand colours in one place (`src/config/brand.ts`)
- [x] 18. Landing blocks as examples: hero, services, gallery, pricing, FAQ, reviews, CTA
- [x] 19. Tables with filters, search, pagination
- [x] 20. Locale-aware formatting of dates, numbers and currency
- [x] 21. Image optimisation

### E. Backend *(be)*
- [x] 22. `/health`
- [x] 23. `/bootstrap` — version, capabilities and languages
- [x] 24. Unified error format: code + message in the user's language
- [x] 25. OpenAPI + generated frontend types kept in sync: `make openapi` writes `openapi.json`, CI checks both sides
- [x] 26. Single form receiver with validation; stub delivery (log/file) without admin
- [x] 27. Server-side form protection: rate limits (`FORMS_RATE_LIMIT`, in-memory) and a honeypot field
- [x] 28. Logs with a request id (`X-Request-ID`)
- [x] 29. CORS for local development

### F. Legal *(fe)*
- [x] 30. Privacy policy, terms, cookie policy — placeholders filled by the owner (`src/config/legal.ts`)
- [x] 31. Cookie banner (when analytics is used): `VITE_ANALYTICS_SCRIPT` loads only after consent

### G. Infrastructure
- [x] 32. One-command development start: `make dev-all` (API + frontend dev server)
- [x] 33. Linter, formatter, type checks (backend: ruff; frontend: Biome + `tsc`)
- [x] 34. Basic tests (backend: pytest; frontend: Vitest unit tests)
- [x] 35. CI (backend: lint, tests incl. `openapi.json`, minimal install, Docker; frontend: lint, types, tests, API types, build)
- [x] 36. Production Docker
- [x] 37. README, developer guide and example settings in English, checked against the code

### Not in minimal (later, as separate capabilities)
JSON-LD, charts, gallery/lightbox, toasts, contacts/social/map, analytics, lead
delivery (email/Telegram/webhook), auto-reply, lead and consent logs, sign-in /
roles / admin, database, files, queues, cart/payments, search, comments,
real-time, CMS.

### Decisions
- Menu and breadcrumbs are basic but free: pages are not tied to the menu.
- The backend is the source of truth for languages (list, enabled, default) and translates its own messages; later managed from the admin.
- Forms work with a stub in minimal; real delivery arrives with the admin.
- Form rate limits are counted in process memory; a shared store (Redis) comes with the scalable profile.
- The frontend commits only generated API *types* (no generated runtime client); requests go through `src/api/*`.
- Forms are described once on the backend (`app/forms.py`): the same description drives server validation and the frontend form.
- `/bootstrap` is the base for languages and capability flags.
- Examples (contact form, data and tables, landing) live in `src/examples` of the frontend and are removed by deleting that folder.
- Legal texts are placeholders with a visible "template" notice until the owner fills `src/config/legal.ts`; analytics is off by default and never loads without consent.
- Frontend tooling: Biome only (lint + format), Vitest unit tests for pure logic; end-to-end tests are not part of minimal.
- i18n: react-i18next. Link previews / SEO: build-time prerender. Languages: `en` (default), `ru`.

## Standard profile (`v0.2.0`, MVP, released 2026-11-10)

Goal: a working *foundation* for every tool, not a full integration. What and why:
[VISION.md](VISION.md); each stage is a few small PRs.

### S0. Ground work *(be)*
- [x] `APP_PROFILE` checked at start: a warning when it does not match the setup
- [x] One initial migration instead of the old history; CI checks migrations against the models
- [x] VISION and ROADMAP in the repository

### S1. Areas and roles *(be, fe)* — after S0
- [x] Public, client and admin areas; admin roles (`root`, `moderator`) land in the admin after sign-in (`areas` in `/auth/users/me`)
- [x] Area switcher in the user menu; route and menu guards on both sides
- [x] Admin area in the same shell with its own menu

### S2. Settings *(be, fe)* — after S1
- [x] Singleton settings: typed groups in JSONB, kept in memory, reloaded every `SETTINGS_REFRESH_SECONDS`
- [x] Admin forms generated from the schemas (Admin → Settings)
- [x] Site name and contacts, languages and the default managed from the admin

### S3. Admin: users *(be, fe)* — after S1
- [x] Users list with search, filters, sorting and pages (`GET /admin/users` in the DataTable query format)
- [x] Block / unblock, change role (`PATCH /admin/users/{id}`)

### S4. Email and tasks *(be, fe)* — after S0
- [x] Celery app; worker service in Docker Compose; the email task as the example
- [x] Mail interface: console backend for development, SMTP for production; translated templates
- [x] Auth: email verification and password reset by email, with frontend pages

### S5. Leads *(be, fe)* — after S2, S4
- [x] Configurable entities: one table `(type, name, params JSONB)`, a Pydantic schema per type, generated admin forms
- [x] Form submissions stored in the database and listed in the admin (Admin → Leads)
- [x] Delivery channels (email, Telegram, webhook) configured as entities, sent by a task (Admin → Channels)

### S6. Files and notifications *(be, fe)* — after S1
- [x] Files: storage interface with local and S3-compatible backends, owner-only access, safe serving; "My files" page
- [x] In-app notifications: model, API, a bell in the header; channel interface for email / Telegram

### S7. OAuth *(be, fe)* — after S1
- [x] Google sign-in end-to-end; providers listed in settings — backend: `/auth/google/*`, `auth_providers` in `/bootstrap` (done); sign-in button

### S8. Release — after all
- [x] Docs per profile; scalable profile: documented differences, readiness check (`/ready`)
- [x] `make migrate` / `make createroot` for Docker; CORS headers on 500 responses
- [x] Pre-release review: safe Google account linking, `SECRET_KEY` check, auth rate limits, background email, no personal data in logs, docs only with `DEBUG`
- [x] Pre-release review *(fe)*: nginx client IP and upload size; admin menu (Settings → General / Channels, Users under Overview); the user area opens Home, client dashboard removed
- [x] Client area renamed to user area *(be, fe)*; one profile page for every role; overview with users, leads per day, channels and the system
- [x] Second review: API docs link only with `DEBUG`, version from the code, broker in `/ready`, clear 413 message
- [x] Release checklist (by hand, needs the owner's accounts):
  - [x] Telegram: a real bot in Admin → Channels — **Test**, then a form submission arrives
  - [x] Google: a real OAuth client — sign up a new user, sign in to an existing account by email
- [x] `v0.2.0`: versions, changelogs, tags and GitHub releases in both repositories

## Account and everyday tools (`v0.3.0`)
- [x] Profile: change name, email (confirmed again) and password *(be, fe)*
- [x] Delete the account with its data (files, notifications); root cannot delete itself *(be, fe)*
- [x] Sign out everywhere: sessions end after a password change or on request (JWT and Redis) *(be, fe)*
- [x] Scheduled tasks: Celery beat in Compose; cleanup example (old notifications, never confirmed accounts) *(be)*
- [x] HTML email layout (site name, button link) with the text version kept *(be)*
- [ ] CSV export of leads and users from the admin tables, with the current filters *(be, fe)*
- [ ] Optional captcha for forms next to the honeypot (an interface, e.g. Cloudflare Turnstile; off by default) *(be, fe)*

## Permissions (`v0.4.0`)
- [ ] Permissions as named actions (e.g. `leads.read`, `users.block`) checked by one dependency
  on the backend and one helper on the frontend, instead of role lists in the code
- [ ] Roles as sets of permissions, edited in the admin; `root` keeps every permission
- [ ] User groups: assign roles to a group, users get the roles of their groups
- [ ] Move the fixed roles (`root`, `moderator`, `user`) to the new model without breaking
  existing projects
- [ ] Audit log of admin actions (who, what, when), shown in the admin

## Production and scalable (`v0.5.0`)
- [ ] Security headers in nginx (HSTS, CSP, X-Frame-Options, Referrer-Policy) *(fe)*
- [ ] HTTPS and a deployment guide for one server (reverse proxy with certificates)
- [ ] Database backups: `make backup` / `make restore`
- [ ] Optional error tracking: Sentry when `SENTRY_DSN` is set (its own requirements file) *(be, fe)*
- [ ] JSON logs for log collectors
- [ ] Form and auth rate limits in Redis for several replicas; local files refused with replicas (use S3)
- [ ] CI: the stack on 3 backend replicas

## Publication (`v1.0.0`)
- [ ] All documentation in English (done for the backend) *(fe)*
- [ ] Quick start: from clone to a running standard stack in 10 minutes
- [ ] `make strip`: physically remove unused modules from a project *(be, fe)*
- [ ] Demo: screenshots in the README or a demo stand
- [ ] CI: Docker smoke test of the whole stack (sign-in, form, upload)
- [ ] Upgrade guide between versions; semver stability promise

## After `v1.0.0`
Fixes, dependency updates and modules from [VISION.md §5](VISION.md#5-not-in-the-template)
(payments, search, comments, real-time, content pages...) when the community or real
projects ask for them.
