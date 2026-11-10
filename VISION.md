# Osnova — what we are building

> Agreed on 2026-11-07, the road to `v1.0.0` on 2026-11-10. It is the reference for the
> roadmap stages; [ROADMAP.md](ROADMAP.md) tracks their status.

## 1. Purpose

Osnova is a **template**, not a product. A developer clones two repositories
(`osnova_backend`, `osnova_frontend`), picks a profile, switches capabilities on in `.env`
and starts writing the project's own pages and endpoints on day one — without spending
the first weeks on layout, languages, forms, auth, admin, Docker and CI.

**For whom:** a developer or a small team making sites and web applications: a landing
page or a company site, an internal tool, a client portal, a SaaS with an admin area.

**MVP** (`v0.2.0`, reached) = the `minimal` and `standard` profiles work exactly as the docs
say, and the template can be shown and offered to others.

**Finished** (`v1.0.0`) = what about 90% of web projects of this kind need is in the template:
every profile, including `scalable`, works as documented; an account manages itself; access
is set with permissions; the app is ready for production (security headers, HTTPS, backups,
error tracking); a new developer starts in minutes. After `v1.0.0` the template changes by
community contributions and long use, not by a plan (section 8).

## 2. Principles

1. **Start small, grow without rewriting.** Moving from `minimal` to `standard` to
   `scalable` changes configuration and infrastructure, not the architecture.
2. **Module = folder.** Each optional capability is one folder on the backend and one on
   the frontend, loaded only when enabled; removing it = deleting the folder.
3. **The backend is the source of truth.** Capabilities, languages, forms and roles come
   from the backend; the frontend builds its routes and UI from `/bootstrap`.
4. **Foundations, not full integrations.** Every tool (email, OAuth, files, tasks,
   notifications) gets a working base with one simple implementation and an interface for
   others — enough for the next developer to start fast.
5. **Lightweight.** Each dependency, bundle chunk and image layer is weighed; nothing is
   loaded for a capability that is off.
6. **Docs match the code.** Every documented feature works; every setting has a default.

## 3. Profiles and capabilities

### How they relate

- A **capability** is a feature flag (`AUTH_ENABLED`, `ADMIN_ENABLED`, ...). It turns a
  module on. Modules have dependencies: `auth` needs `db`, `admin` and `files` need `auth`.
- A **profile** is the infrastructure the app runs on:

| Profile | Infrastructure | Capabilities possible |
|---|---|---|
| `minimal` | the app only: no database, Redis or workers | only those that need no datastore (today: none of the optional ones) |
| `standard` | + PostgreSQL, Redis, Celery worker | all |
| `scalable` | `standard` + several backend replicas (+ later: load balancer, monitoring) | all, and they must work with several replicas |

So `minimal` **does** use the capability mechanism (`/bootstrap`, flags, lazy modules), but
all optional capabilities are off because each of them needs a database. Turning on
`AUTH_ENABLED` means moving to `standard`.

**Decision:** `APP_PROFILE` stays and is checked at start: a warning when it does not match
the setup (e.g. `minimal` with a `DATABASE_URL`, `standard` without one). Auth always needs
PostgreSQL, so it is a `standard` capability (no SQLite mode).

### Minimal — a site without a database (released `v0.1.0`, 2026-11-07)

- App shell: header, collapsible left menu, footer, mobile menu, breadcrumbs, page states,
  404 / error pages
- Languages (`en`, `ru`) in files and in the URL; translated backend messages
- SEO: per-page tags, `hreflang`, link previews (prerender), `sitemap.xml`, `robots.txt`
- Forms described on the backend: validation, rate limit, honeypot, stub delivery (log / file)
- Theme and brand in one file; landing blocks; tables; locale formatting; images
- Legal pages; cookie banner when analytics is on
- Unified errors, request ids, health check, OpenAPI → frontend types
- Docker, CI, linters, tests, `make dev-all`
- Examples in one folder that can be deleted

### Standard — an application with users (MVP, released `v0.2.0`, 2026-11-10)

**Areas and roles**

- **Public area** — pages for everyone (as in minimal).
- **User area** — for signed-in users: profile, the project's own pages; it starts on home.
- **Admin area** — for `root` and `moderator`: after sign-in they land here and can switch
  to the user area; other users never see it.

**Foundations**

| Tool | What the template gives |
|---|---|
| Database | PostgreSQL, async SQLAlchemy, Alembic with clean migration history |
| Auth | sign-up, sign-in, sign-out; JWT cookie by default, Redis sessions optional; email verification and password reset by email |
| Roles | `user`, `moderator`, `root`; route and menu guards on both sides |
| Admin | users (search, block / unblock, change role), form submissions, lead delivery, site settings; the admin layout to add own sections |
| Settings | typed settings edited in the admin (see below); `.env` keeps infrastructure and secrets |
| Email | sending interface; console backend for development, SMTP for production; templates translated |
| Files | upload / download with limits; local storage; interface for S3-compatible storage |
| Background tasks | Celery app and a worker service in Docker Compose; one example task (e.g. sending email) |
| Notifications | in-app notifications: model, API, a bell in the header; a channel interface so email / Telegram can be added later |
| OAuth | Google wired end-to-end; adding another provider is configuration |
| Leads | form submissions stored and shown in the admin; delivery (email / Telegram / webhook) set up in the admin |

**Settings in the admin**

Settings the site owner changes at runtime live in the database; `.env` keeps what needs a
restart (infrastructure, secrets, capability flags) and gives defaults.

- **Singleton settings** — one typed group per topic (`site`, `forms`, `users`...), described
  in code as a Pydantic model with defaults and stored as one JSONB row per group. Adding a
  field needs no migration; reading is typed (`settings.get(SiteSettings).contact_email`)
  and cached in process; each process reloads after a short interval, so replicas agree
  without a shared cache.
- **Configurable entities** — lists of similar records (lead delivery channels, countries) in one generic table `(type, name, params JSONB)` with a Pydantic schema per type,
  so a new kind of entity is a class, not a table and a migration. Entities that need
  relations or heavy queries become ordinary tables.
- **Admin UI is generated** from the schemas: the same field description that drives
  `SchemaForm` renders the edit form, so a new setting appears in the admin without frontend
  code.
- First users: site name and contacts, enabled languages and the default (a singleton group:
  a language also needs translation files; `.env` stays as the initial value), lead
  delivery channels (entities, with S5).

### Scalable (after MVP)

Documented differences from `standard`, readiness check, shared rate-limit store in
Redis, everything stateless (no local files or in-memory state that breaks with replicas).

## 4. Interface layout (both areas)

```
┌──────────────────────────────────────────────────────────────┐
│ [≡] Logo / name                      lang · theme · 🔔 · user │  header
├────────────┬─────────────────────────────────────────────────┤
│ Home       │                                                 │
│ Examples   │   page: title, actions, breadcrumbs, content    │
│ Dashboard  │                                                 │
│ ...        │                                                 │
│ [«]        │                                                 │
├────────────┴─────────────────────────────────────────────────┤
│ © year name                       privacy · terms · cookies  │  footer
└──────────────────────────────────────────────────────────────┘
```

- Left menu, open by default on desktop; collapses to icons; the choice is remembered.
- On phones the same menu opens as a drawer from `[≡]`.
- The header right side holds global actions: language, theme, later notifications and the
  user menu (profile, switch area, sign out).
- The menu can still be moved to the top or turned off in `src/config/navigation.ts`.
- The admin area uses the same shell with its own menu.

## 5. Not in the template

Needed by some kinds of projects, not by nearly all of them, so they would only make the
template heavier: payments and cart, full-text search (tables already search and filter),
comments, real-time, a CMS or content pages, two-factor sign-in, image processing,
analytics dashboards, multi-tenancy, microservices. They can become separate modules later,
from the community or after long use. Reviewed on 2026-11-10: of the "maybe" group only a
captcha made it in (section 8).

## 6. Decisions (2026-11-07)

1. `APP_PROFILE` is checked against the setup at start (warning on mismatch).
2. Auth always needs PostgreSQL: it is part of `standard`, no SQLite mode.
3. Admin for MVP: users, form submissions, lead delivery and site settings (typed settings
   and configurable entities, see section 3).
4. OAuth foundation: Google.
5. Notifications for MVP: in-app, with a channel interface for email / Telegram later.
6. `v0.1.0` released after the menu changes.

## 7. Standard stages (`v0.2.0`)

Each stage is a few small PRs; ROADMAP tracks the items.

| Stage | Content | Depends on |
|---|---|---|
| **S0. Ground work** | `APP_PROFILE` check; one clean initial migration instead of the current history; VISION and ROADMAP in the repo | — |
| **S1. Areas and roles** | public / user / admin areas, landing by role after sign-in, area switcher in the user menu, guards on both sides; admin uses the same shell with its own menu | S0 |
| **S2. Settings** | singleton settings (models, cache, API), generated admin forms; site settings, languages from the admin | S1 |
| **S3. Admin: users** | list with search and filters, block / unblock, change role | S1 |
| **S4. Email and tasks** | mail interface (console / SMTP), translated templates, Celery worker in Compose; email verification and password reset pages | S0 |
| **S5. Leads** | configurable entities; submissions stored in the database, admin list, delivery channels (email, Telegram, webhook) configured as entities, sent by a task | S2, S4 |
| **S6. Files and notifications** | storage interface (local / S3-compatible); in-app notifications with a bell and a channel interface | S1 |
| **S7. OAuth** | Google sign-in end-to-end, provider list in settings | S1 |
| **S8. Release** | docs per profile, scalable differences, readiness check, `v0.2.0` | all |

## 8. Road to `v1.0.0` (agreed 2026-11-10)

What almost every project with users needs, then production, then publication. Each stage
is a release; ROADMAP tracks the items.

| Release | Content | Why it is basic |
|---|---|---|
| **`v0.3.0` Account and everyday tools** | change password, email and name; delete the account; sign out everywhere; scheduled tasks (Celery beat) with a cleanup example; HTML email layout; CSV export of leads and users; optional captcha next to the honeypot | a user area without self-service looks unfinished; deleting an account is a legal requirement (GDPR, 152-FZ); every live project collects data to clean and owners export leads to a spreadsheet |
| **`v0.4.0` Permissions** | permissions as named actions, roles as sets of them edited in the admin, user groups, a smooth move from the fixed roles; an audit log of admin actions | three roles in the code stop fitting as soon as a team grows; "who did this?" comes with the second admin |
| **`v0.5.0` Production and scalable** | security headers, HTTPS and a deployment guide, database backups (`make backup` / `make restore`), optional error tracking (Sentry when `SENTRY_DSN` is set), JSON logs, the form and auth rate limits in Redis, a check on 3 replicas in CI | every project is deployed; `scalable` is documented and must actually work with replicas |
| **`v1.0.0` Publication** | all docs in English, a 10-minute quick start, `make strip` to remove unused modules, a demo (screenshots or a stand), a Docker smoke test of the whole stack in CI, an upgrade guide between versions, semver stability promise | a stranger can take it and trust it |

Weight stays a rule for every stage: no new heavy dependency is loaded for a capability
that is off; optional integrations (Sentry, captcha) are installed only when used.

**After `v1.0.0`:** fixes, dependency updates and modules from section 5 when the community
or real projects ask for them.

