# Roadmap

Osnova is released in two steps: **minimal** first, then **standard**.
MVP = both profiles work as documented and the template can be offered to others.

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

## Standard profile (`v0.2.0`, MVP)

Goal: a working *foundation* for every tool, not a full integration. What and why:
[VISION.md](VISION.md); each stage is a few small PRs.

### S0. Ground work *(be)*
- [x] `APP_PROFILE` checked at start: a warning when it does not match the setup
- [x] One initial migration instead of the old history; CI checks migrations against the models
- [x] VISION and ROADMAP in the repository

### S1. Areas and roles *(be, fe)* — after S0
- [ ] Public, client and admin areas; admin roles (`root`, `moderator`) land in the admin after sign-in
- [ ] Area switcher in the user menu; route and menu guards on both sides
- [ ] Admin area in the same shell with its own menu

### S2. Settings *(be, fe)* — after S1
- [ ] Singleton settings (typed groups in JSONB) and configurable entities, cached
- [ ] Admin forms generated from the schemas
- [ ] Site name and contacts, languages and the default managed from the admin

### S3. Admin: users *(be, fe)* — after S1
- [ ] Users list with search and filters
- [ ] Block / unblock, change role

### S4. Email and tasks *(be, fe)* — after S0
- [~] Celery app (done); worker service in Docker Compose, one example task
- [ ] Mail interface: console backend for development, SMTP for production; translated templates
- [~] Auth: JWT by default, Redis sessions optional (done); email verification and password reset pages

### S5. Leads *(be, fe)* — after S2, S4
- [ ] Form submissions stored in the database and listed in the admin
- [ ] Delivery channels (email, Telegram, webhook) configured as entities, sent by a task

### S6. Files and notifications *(be, fe)* — after S1
- [~] Safe local storage (done); storage interface for S3-compatible backends
- [ ] In-app notifications: model, API, a bell in the header; channel interface for email / Telegram

### S7. OAuth *(be, fe)* — after S1
- [ ] Google sign-in end-to-end; providers listed in settings

### S8. Release — after all
- [ ] Docs per profile; scalable profile: documented differences, readiness check
- [ ] `v0.2.0`

## Later
- All documentation, instructions and code comments in English (done for the backend)
- `osnova strip --profile minimal`: physically remove unused modules from a project
