# Database migrations (Alembic)

Run the commands from the repository root with `DATABASE_URL` set (in `.env` or the
environment). `migrations/env.py` imports every model module; add a new one there.

## Commands

```bash
alembic upgrade head                                # apply all migrations
alembic revision --autogenerate -m "add projects"   # new migration from the models
alembic check                                       # fail if the models need a migration
alembic downgrade -1                                # roll back one migration
alembic current                                     # revision of the database
alembic history                                     # list of migrations
```

## Rules

1. Generate migrations with `--autogenerate`, then read the file and fix what Alembic
   cannot know: data changes, renames (autogenerate sees a drop + add), PostgreSQL enum
   types (drop them in `downgrade`).
2. Keep `downgrade` working: CI runs `upgrade head`, `alembic check` and `downgrade base`.
3. Never edit or delete a migration that is already applied somewhere; add a new one.
4. One change per migration, with a short message.

## History

The history starts with `0001_initial_schema` (`v0.2.0`). A database created by the
earlier migrations has the same schema; mark it as up to date once:

```bash
alembic stamp --purge 0001
```
