# Deploying to one server

Osnova runs on a single Linux server with Docker Compose: the standard profile
(PostgreSQL, Redis, the Celery worker and beat) behind Caddy, which gets and renews
HTTPS certificates from Let's Encrypt. This guide takes a fresh server to a running
site; the [README](README.md#docker) explains the parts.

```
visitor ──https──▶ Caddy :443 ──▶ /api/*  backend (one or more replicas)
                    (:80 → https)  ▶ the rest  frontend nginx (site, security headers)
```

## 1. Server and domain

- A Linux server with 2 GB of memory or more (the frontend build needs it), Docker
  Engine and the Compose plugin ([docs.docker.com/engine/install](https://docs.docker.com/engine/install/)),
  `git` and `make`.
- A DNS `A` record (and `AAAA` for IPv6) of your domain pointing to the server. Let's
  Encrypt checks it, so set it before the first start.
- Open ports 22 (SSH), 80 and 443 (TCP, and UDP 443 for HTTP/3), close the rest, e.g.:

  ```bash
  sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443 && sudo ufw enable
  ```

  Ports published by Docker bypass `ufw`; the stack publishes only 80 and 443.

## 2. Code and settings

```bash
sudo mkdir -p /srv && sudo chown "$USER" /srv && cd /srv
git clone https://github.com/rastal88/osnova_backend.git
git clone https://github.com/rastal88/osnova_frontend.git
cd osnova_backend
cp .env.example .env
```

Production values in `.env` (the rest of `.env.example` keeps its defaults):

| Variable | Value |
|---|---|
| `APP_PROFILE` | `standard` |
| `DEBUG` | `false` (no `/docs` in production) |
| `SITE_URL` | `https://example.com`: Caddy takes the certificate for this host; links in emails, canonical links and the sitemap use it too |
| `SECRET_KEY` | a long random value: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` — keep a copy, stored secrets are encrypted with it |
| `POSTGRES_PASSWORD` | a random value of its own (set before the first start: it is applied when the database is created) |
| `AUTH_ENABLED`, `ADMIN_ENABLED`, ... | the capabilities you need |
| `COOKIE_SECURE` | `true` |
| `LOG_FORMAT` | `json` if a log collector reads the logs |
| `MAIL_BACKEND`, `SMTP_*` | your SMTP server (later in Admin → Settings → Mail) |
| `SENTRY_DSN`, `EXTRA_REQUIREMENTS=sentry`, `FRONTEND_SENTRY_DSN` | optional error tracking (section 6) |

`.env` holds secrets: `chmod 600 .env`, never commit it.

## 3. First start

```bash
make up-standard HTTPS=1     # builds the images, starts everything with Caddy
make migrate                 # creates the tables
make createroot              # the first root user (asks for the email and password)
```

Open `https://example.com`. The certificate arrives within a minute of the first
start; `docker logs osnova-caddy-1` shows the progress. Every `make` command that starts
or stops containers (`up-*`, `down`) needs `HTTPS=1` too; `export HTTPS=1` in the shell
profile of the deploy user saves typing it.

With several backend replicas use `make up-scalable HTTPS=1` and files in S3
(`FILES_STORAGE=s3`); Caddy spreads API requests over the replicas.

## 4. Backups

```bash
make backup                  # backups/osnova-<date>.dump (+ -files.tar.gz)
```

Every night from cron (`crontab -e` of a user in the `docker` group):

```cron
0 3 * * * cd /srv/osnova_backend && make backup KEEP_DAYS=14 >> backups/backup.log 2>&1
```

Copy `backups/` to another host or bucket as well (`rsync`, `rclone`). Restoring:
`make restore FILE=backups/...` ([README → Backups](README.md#backups)). Keep a copy of
`.env` somewhere safe too: its `SECRET_KEY` decrypts the stored secrets. Certificates
need no backup, Caddy simply gets new ones.

## 5. Updates

```bash
cd /srv/osnova_backend && git pull && git -C ../osnova_frontend pull
make backup
make up-standard HTTPS=1     # rebuilds the changed images, restarts them
make migrate
```

Read the CHANGELOG of both repositories first: it lists new settings and changes that
need a step from you.

## 6. Error tracking (optional)

Create two projects in Sentry (or a self-hosted GlitchTip): one for the backend, one for
the browser. In `.env`:

```bash
SENTRY_DSN=https://<key>@<host>/<backend project>
EXTRA_REQUIREMENTS=sentry    # installs requirements/sentry.txt into the images
FRONTEND_SENTRY_DSN=https://<key>@<host>/<frontend project>
SENTRY_ENVIRONMENT=production
```

and rebuild: `make up-standard HTTPS=1`. No personal data is sent (README → Development →
Error tracking; frontend DEVELOPMENT.md → Error tracking).

## 7. When something is wrong

- **No certificate:** `docker logs osnova-caddy-1`. The DNS record must point to this
  server and ports 80 and 443 must be reachable from the internet; Let's Encrypt limits
  failed attempts, so fix the cause before restarting many times.
- **502 from the API:** the backend is not healthy yet or crashed:
  `make ps HTTPS=1`, `docker logs osnova-backend-1` (a missing setting stops it with a
  message).
- **`/api/v1/ready` answers 503:** the database or Redis is not reachable.
- **Everyone hits the rate limit together:** something in front of Caddy (a load
  balancer, Cloudflare proxy) hides the visitors' addresses. Add its addresses to
  `trusted_proxies` in `deploy/Caddyfile` ([Caddy docs](https://caddyserver.com/docs/caddyfile/options#trusted-proxies)).
- **A browser blocks something:** the console names the Content Security Policy
  directive; add the host with `CSP_EXTRA_ORIGINS` and rebuild.

Another reverse proxy instead of Caddy (Traefik, nginx with certbot, a cloud load
balancer) works the same way: terminate HTTPS, send `/api/*` to `backend:8000` with
`X-Forwarded-For` set to the visitor's address (not appended to) and
`X-Forwarded-Proto: https`, the rest to `frontend:80`.
