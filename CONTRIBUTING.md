# Contributing

Thanks for helping with Osnova! The project has two repositories:
[osnova_backend](https://github.com/rastal88/osnova_backend) (this one) and
[osnova_frontend](https://github.com/rastal88/osnova_frontend). Plans live in
[ROADMAP.md](ROADMAP.md).

## Setup

```bash
make install          # venv + requirements/dev.txt
cp .env.example .env
make dev              # API on http://localhost:8000, docs at /docs
make dev-all          # API + frontend dev server (../osnova_frontend), Ctrl+C stops both
```

Full stack in Docker (both repositories side by side): `make up-minimal` or `make up-standard`.

## Workflow

1. Create a branch from `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
2. Use [Conventional Commits](https://www.conventionalcommits.org/):
   `feat: add language list to bootstrap`, `fix(files): reject unknown names`.
3. Before pushing: `make lint` and `make test`.
4. Open a pull request using the template. CI must be green.
5. Note user-visible changes in [CHANGELOG.md](CHANGELOG.md) under *Unreleased*.

## Architecture rules

- **Module = folder.** An optional capability lives in `app/modules/<name>/` and exposes
  `register(app)`. It is registered in `app/core/modules.py` and imported only when enabled.
- The core (`app/core`) never imports a module. A module may import only the modules it
  lists in `requires`.
- A module's dependencies go to `requirements/<name>.txt` and are included in `standard.txt`.
- Each new setting gets a default in `app/config.py` and an entry in `.env.example`.
- Database schema changes go through Alembic migrations only.

## Tests

`pytest` runs with all modules enabled. `tests/test_modules.py` checks in a separate process
that the minimal profile imports none of the optional packages — keep it passing.
