# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Capabilities (`*_ENABLED` flags) and `GET /api/v1/bootstrap`, `GET /api/v1/health`.
- Module registry: optional capabilities in `app/modules/*` are imported only when enabled,
  with dependency checks between modules.
- Per-module requirements in `requirements/`; the minimal image installs only `base.txt`.
- Docker Compose profiles `minimal` / `standard` / `scalable`, Makefile commands.
- `AUTH_STRATEGY`: JWT sessions by default, Redis optional.
- Files module: authenticated upload, server-generated names, `FILES_MAX_SIZE_MB` limit.
- CI: ruff, tests, minimal-install check, Docker builds. Open-source repository files.

### Changed
- Every setting has a default; an empty `.env` runs the minimal profile.
- `user_flow` is registered only with auth and is open to every signed-in role.
- Database schema is created only by Alembic migrations.

### Removed
- Unused OAuth placeholder and `OAUTH2_*` settings (OAuth returns in the standard stage).

### Security
- Fixed path traversal in file download/upload.
- Password reset tokens are no longer logged outside `DEBUG`.
