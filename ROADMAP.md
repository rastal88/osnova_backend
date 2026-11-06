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

## Minimal profile (`v0.1.0`)

### A. Layout and navigation *(fe)*
- [~] 1. App shell: header, footer, mobile menu; menu can be disabled and placed top/left/right (configurable *style* still missing)
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
- [~] 14. Form generated from a field description *(be, fe)* — description served by `GET /forms/{name}`
- [~] 15. Client and server validation with clear per-field errors *(fe, be)* — server side done
- [ ] 16. Submit states (sending / success / error / retry) and a consent checkbox *(fe)*

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
- [~] 25. OpenAPI + generated frontend client kept in sync (config exists, not checked in CI)
- [x] 26. Single form receiver with validation; stub delivery (log/file) without admin
- [ ] 27. Server-side form protection: rate limits and anti-spam
- [ ] 28. Logs with a request id
- [x] 29. CORS for local development

### F. Legal *(fe)*
- [ ] 30. Privacy policy, terms, cookie policy — placeholders filled by the owner
- [ ] 31. Cookie banner (when analytics is used)

### G. Infrastructure
- [~] 32. One-command development start (`make dev` on the backend; frontend separately)
- [~] 33. Linter, formatter, type checks (backend: ruff; frontend: one tool still to choose)
- [~] 34. Basic tests (backend yes, frontend none)
- [~] 35. CI (backend: lint, tests, minimal install, Docker; frontend: build only)
- [x] 36. Production Docker
- [~] 37. README and example settings (to be rewritten in English)

### Not in minimal (later, as separate capabilities)
JSON-LD, charts, gallery/lightbox, toasts, contacts/social/map, analytics, lead
delivery (email/Telegram/webhook), auto-reply, lead and consent logs, sign-in /
roles / admin, database, files, queues, cart/payments, search, comments,
real-time, CMS.

### Decisions
- Menu and breadcrumbs are basic but free: pages are not tied to the menu.
- The backend is the source of truth for languages (list, enabled, default) and translates its own messages; later managed from the admin.
- Forms work with a stub in minimal; real delivery arrives with the admin.
- Forms are described once on the backend (`app/forms.py`): the same description drives server validation and the frontend form.
- `/bootstrap` is the base for languages and capability flags.
- Examples (contact form, data and tables, landing) live in `src/examples` of the frontend and are removed by deleting that folder.
- i18n: react-i18next. Link previews / SEO: build-time prerender. Languages: `en` (default), `ru`.

## Standard profile (`v0.2.0`, MVP)

Goal: a working *foundation* for every tool, not a full integration.

- [ ] Client area and admin area: admin roles land in the admin after login and can switch to the client area; other users see only the client area; public pages stay public
- [ ] Admin: users list and basic management
- [~] Database: Alembic only (done), migration hygiene
- [~] Auth sessions: JWT by default, Redis optional (done); email verification and password reset via email
- [ ] Email sending abstraction (console backend for development)
- [~] Files: safe local storage (done); storage interface for S3-compatible backends
- [~] Background tasks: Celery app (done); worker service in Docker Compose
- [ ] Notifications foundation
- [ ] OAuth foundation
- [ ] Lead delivery configured from the admin
- [ ] Scalable profile: documented differences, health/readiness checks

## Later
- All documentation, instructions and code comments in English
- `osnova strip --profile minimal`: physically remove unused modules from a project
