# Osnova

**Универсальный full-stack шаблон для быстрой разработки и запуска web-приложений на Python и React.**

Osnova предоставляет готовую архитектуру и набор стандартных решений, покрывающих типовые
задачи разработки, развёртывания и эксплуатации web-приложения — от небольших
информационных сайтов и простых API до полноценных нагруженных систем.

> **Главный принцип:** Osnova ускоряет разработку нового проекта, не ограничивая его
> дальнейшее развитие. Приложение, начатое как `minimal`, может постепенно перейти к
> `standard` и `scalable` без переписывания фундаментальной архитектуры.

Состоит из двух независимых репозиториев, взаимодействующих исключительно через API:

| Репозиторий | Назначение | Стек |
|---|---|---|
| **osnova_backend** (этот репозиторий) | API, бизнес-логика, данные | Python · FastAPI · SQLAlchemy · PostgreSQL |
| [**osnova_frontend**](https://github.com/<org>/osnova_frontend) | Web-интерфейс (SPA) | React · TypeScript · Vite |

---

## Содержание

- [Основные принципы](#основные-принципы)
- [Профили приложения](#профили-приложения)
- [Архитектура и capabilities](#архитектура-и-capabilities)
- [Технологический стек](#технологический-стек)
- [Структура проекта](#структура-проекта)
- [Быстрый старт](#быстрый-старт)
- [Развёртывание (Docker)](#развёртывание-docker)
- [Конфигурация](#конфигурация)
- [API](#api)
- [Разработка](#разработка)
- [Связанные проекты](#связанные-проекты)

---

## Основные принципы

- **Универсальность** — шаблон не привязан к конкретному типу приложения.
- **Модульность** — функциональность подключается по необходимости.
- **Единая архитектура** — разные уровни приложения не требуют разных кодовых баз.
- **Масштабируемость** — приложение растёт без архитектурного переписывания.
- **Конфигурируемость** — окружение и возможности управляются конфигурацией.
- **Разделение ответственности** — frontend, backend и инфраструктура независимы.
- **Простота запуска** — новый проект быстро разворачивается из шаблона.
- **Production-ready** — архитектура изначально учитывает разработку, тестирование,
  развёртывание и эксплуатацию.
- **Modular monolith** — приложение начинается как модульный монолит; микросервисы
  не являются обязательной частью.

---

## Профили приложения

Один и тот же код поддерживает три профиля. Переход между ними не требует переписывания —
меняется только конфигурация и подключаемая инфраструктура.

### Minimal

```
Frontend ──▶ FastAPI ──▶ PostgreSQL (optional)
```

Для сайтов, информационных приложений, небольших сервисов, простых API и внутренних
инструментов. Не требует Redis, воркеров и другой дополнительной инфраструктуры.

### Standard

```
                 ┌───── PostgreSQL
Frontend ──▶ FastAPI
                 ├───── Workers
                 ├───── Redis
                 └───── Storage
```

Основной production-профиль для большинства полноценных приложений. Может включать
пользователей, authentication, authorization, Admin, фоновые задачи, email, файловое
хранилище, кеширование, notifications.

### Scalable

```
                Load Balancer
                 /          \
            FastAPI        FastAPI
                 \          /
                  PostgreSQL
                      │
                    Redis
                      │
                   Workers
```

Для приложений, которым нужно горизонтальное масштабирование: несколько экземпляров
backend, load balancing, масштабирование воркеров, CDN, object storage, расширенное
кеширование, мониторинг. При этом приложение не превращается в микросервисы.

---

## Архитектура и capabilities

Ядро конфигурируемости — механизм **capabilities**. Возможности приложения управляются
флагами окружения, агрегируются на бэкенде и передаются на фронтенд.

```
   .env (флаги)          capabilities.py          bootstrap.py             Frontend
   
 AUTH_ENABLED        ──▶  Capabilities     ──▶   GET /api/v1/bootstrap ──▶ BootstrapStore
 ADMIN_ENABLED            dataclass              { profile, features }      ▼
 FILES_ENABLED                                                             UI + routing
 NOTIFICATIONS_ENABLED
 BACKGROUND_TASKS_ENABLED
```

### Правило источника истины

> **Backend — единственный источник истины о доступных возможностях.**
> Frontend строит маршрутизацию и UI из capability-конфигурации, полученной
> через `GET /api/v1/bootstrap`. Если capability выключена, соответствующие роуты и
> элементы интерфейса на фронтенде не создаются.

| Capability | `false` — frontend не создаёт |
|---|---|
| `authentication` | роуты `/login`, `/register`; редиректы в `ProtectedRoute` |
| `admin` | секцию `/admin` и пункты меню администратора |
| `files` | компоненты загрузки/скачивания файлов |
| `notifications` | центр уведомлений |
| `background_tasks` | (как правило, UI не затрагивает) |

При `authentication = false` приложение работает как публичный сайт: все страницы
доступны, точки входа auth отсутствуют.

Соответствие флагов профилям:

| Capability | Minimal | Standard | Scalable |
|---|:---:|:---:|:---:|
| `AUTH_ENABLED` | ✕ (optional) | ✓ | ✓ |
| `ADMIN_ENABLED` | ✕ | ✓ | ✓ |
| `FILES_ENABLED` | ✕ | optional | ✓ |
| `NOTIFICATIONS_ENABLED` | ✕ | ✓ | ✓ |
| `BACKGROUND_TASKS_ENABLED` | ✕ | ✓ | ✓ |
| Redis / Workers | ✕ | ✓ | ✓ |
| Load Balancer / CDN | ✕ | ✕ | ✓ |

---

## Технологический стек

**Backend**

- Python 3.13, FastAPI, Uvicorn
- SQLAlchemy 2.0 (async), Alembic, asyncpg
- PostgreSQL
- `fastapi-users` — аутентификация, JWT/cookie, роли
- Celery + Redis — фоновые задачи (опционально)
- Pydantic v2 / pydantic-settings — конфигурация и валидация

**Frontend** — см. [osnova_frontend](https://github.com/<org>/osnova_frontend)

- React 19, TypeScript, Vite
- Zustand — управление состоянием
- Ant Design — UI
- Axios, React Router
- Biome, Playwright

**Инфраструктура (DevOps)**

- Docker / Docker Compose с профилями `minimal` / `standard` / `scalable`
- Nginx — раздача SPA и reverse proxy на backend
- CI/CD — GitHub Actions (тесты backend, сборка frontend)
- Environment configuration, структурированное логирование, health checks
- Мониторинг — планируется (см. профиль `scalable`)

---

## Структура проекта

```
osnova_backend/
├── app/
│   ├── core/            # ядро (всегда): middleware, capabilities, bootstrap,
│   │                    # health, реестр модулей (modules.py)
│   ├── modules/         # опциональные модули — каждый в своей папке
│   │   ├── db/          # SQLAlchemy (async), сессии          ← DATABASE_URL
│   │   ├── auth/        # fastapi-users, роли, модель User    ← AUTH_ENABLED
│   │   ├── admin/       # эндпоинты администратора            ← ADMIN_ENABLED
│   │   ├── files/       # загрузка/скачивание файлов          ← FILES_ENABLED
│   │   └── tasks/       # Celery                              ← BACKGROUND_TASKS_ENABLED
│   ├── user_flow/       # пример прикладного домена (клиентская часть)
│   ├── config.py        # настройки (pydantic-settings)
│   └── __init__.py      # фабрика приложения
├── migrations/          # Alembic-миграции
├── requirements/        # зависимости по модулям: base, db, auth, files, tasks, redis,
│                        # standard (всё), dev (всё + тесты и линтер)
├── tests/               # тесты
├── alembic.ini
├── pyproject.toml       # настройки ruff и pytest
├── Dockerfile           # образ backend (ARG REQUIREMENTS=base|standard)
├── docker-compose.yml   # базовый (minimal-safe) compose
├── docker-compose.datastores.yml  # override: postgres + redis (standard/scalable)
├── Makefile             # up-minimal / up-standard / up-scalable
└── manage.py
```

---

## Быстрый старт

### Требования

- Python 3.13
- PostgreSQL (опционально для minimal)

### Установка

```bash
git clone <repo-url>
cd osnova_backend
python3.13 -m venv venv && source venv/bin/activate
pip install -r requirements/dev.txt     # все модули + инструменты разработки
# или только то, что нужно, например minimal:
# pip install -r requirements/base.txt
```

### Настройка базы

```sql
\c <db_name>
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Конфигурация

```bash
cp .env.example .env   # заполните значения
```

У всех переменных есть значения по умолчанию, поэтому пустой `.env` запускает профиль
`minimal`: без БД, Redis и без загрузки кода опциональных модулей.

Если включённому модулю не хватает зависимости (например, `AUTH_ENABLED=true` без
`DATABASE_URL`), приложение не стартует и пишет, чего не хватает.

### Миграции и первый root

> Выполняются только при включённой аутентификации и настроенной БД.

```bash
alembic upgrade head
python manage.py createroot
```

### Запуск

```bash
make dev                       # = python run.py, host/port из .env (APP_HOST / APP_PORT)
# или
./run.sh -h 0.0.0.0 -p 8000    # с явным указанием host/port
```

Документация API: `http://localhost:8000/docs`

---

## Развёртывание (Docker)

Деплой построен на **Docker Compose profiles**: одна кодовая база разворачивается в
одном из трёх профилей без изменения кода.

### Требования

- Docker и Docker Compose v2
- Оба репозитория рядом: `osnova_backend/` и `osnova_frontend/` в одной директории

### Команды

```bash
cp .env.example .env          # заполните значения (единственный env-файл)
make up-minimal               # backend + frontend (без БД/Redis)
make up-standard              # + postgres + redis
make up-scalable              # standard + горизонтальное масштабирование
make logs                     # логи
make down                     # остановить
```

Эквивалент без `make`:

```bash
# minimal
docker compose -f docker-compose.yml --profile minimal up --build -d
# standard
docker compose -f docker-compose.yml -f docker-compose.datastores.yml \
               --profile standard up --build -d
```

### Доступ

Наружу публикуется только frontend; API и документация доступны через него (один origin).

| Ресурс | URL |
|---|---|
| Frontend | `http://localhost:8080` |
| Backend API | `http://localhost:8080/api/v1` |
| Swagger UI | `http://localhost:8080/docs` |

### Как устроено

- **Frontend** собирается из `osnova_frontend` (Node build → nginx) и проксирует `/api`,
  `/docs`, `/openapi.json`, `/redoc` на сервис `backend`. Один origin — CORS не нужен.
- **Backend** — многоэтапный образ, non-root, запускается через `uvicorn`. Порт `8000`
  доступен только внутри compose-сети (не публикуется на хост) — это позволяет
  масштабировать реплики без конфликта портов.
- **Профили** включают сервисы: `postgres`, `redis` вынесены в
  `docker-compose.datastores.yml` и помечены `standard`/`scalable`; `backend` и
  `frontend` — всеми профилями. При `--profile minimal` образы `postgres` и `redis`
  не загружаются и не запускаются.
- **Адреса БД/Redis** не задаются вручную: базовый compose для `minimal` явно
  выставляет `DATABASE_URL`/`REDIS_URL` пустыми, а для `standard`/`scalable`
  override-файл подставляет внутренние адреса сервисов (`postgres:5432`,
  `redis:6379`). Локальные значения `localhost` из `.env` не используются.
- **Health checks**: backend отдаёт `GET /api/v1/health`; postgres/redis — встроенные.
- **Переменные**: флаги возможностей и секреты — в `.env` (см. `.env.example`).
- **Миграции**: при `RUN_MIGRATIONS=true` и заданном `DATABASE_URL` entrypoint выполняет
  `alembic upgrade head` до старта приложения.

### Особенности профилей

- `minimal` — публичный сайт без БД: отдаётся статика SPA и публичные API. Из
  инфраструктуры поднимаются только `backend` и `frontend`; обращений к БД/Redis нет.
- `standard` — в `.env` выставьте `APP_PROFILE=standard` и включите нужные флаги
  (`AUTH_ENABLED`, `ADMIN_ENABLED`, `BACKGROUND_TASKS_ENABLED`). Учётные данные БД
  (`POSTGRES_USER/PASSWORD/DB`) опциональны — по умолчанию `osnova/osnova/osnova`.
- `scalable` — те же образы, масштабирование реплик. Backend не публикует порт на хост,
  а nginx в frontend балансирует через внутренний DNS Docker:
  `docker compose -f docker-compose.yml -f docker-compose.datastores.yml \
  --profile scalable up --scale backend=3`.

---

## Конфигурация

Основные переменные окружения (см. `.env.example` и `app/config.py`):

| Переменная | Описание |
|---|---|
| `APP_NAME`, `APP_VERSION`, `APP_PROFILE` | Идентификация и профиль приложения |
| `APP_HOST`, `APP_PORT`, `DEBUG` | Хост, порт, режим отладки |
| `DATABASE_URL`, `DB_ECHO` | Подключение к БД (включает модуль `db`), логирование SQL |
| `SECRET_KEY`, `ALGORITHM` | Подпись токенов (обязателен `SECRET_KEY` при `AUTH_ENABLED`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни сессии и cookie |
| `AUTH_STRATEGY` | `jwt` (по умолчанию, без Redis) или `redis` (нужен `REDIS_URL`) |
| `COOKIE_SECURE` | Флаг `Secure` у auth-cookie (включать только при HTTPS) |
| `CORS_ORIGINS` | Разрешённые origin'ы через запятую (для локальной разработки) |
| `REDIS_URL` | Redis (сессии при `AUTH_STRATEGY=redis`) |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Celery (обязателен брокер при `BACKGROUND_TASKS_ENABLED`) |
| `FILES_DIR`, `FILES_MAX_SIZE_MB` | Папка и лимит размера для модуля файлов |
| `AUTH_ENABLED` | Аутентификация и регистрация (нужен модуль `db`) |
| `ADMIN_ENABLED` | Административная панель (нужен `AUTH_ENABLED`) |
| `FILES_ENABLED` | Файловое хранилище (нужен `AUTH_ENABLED`) |
| `NOTIFICATIONS_ENABLED` | Уведомления (пока только флаг для фронтенда) |
| `BACKGROUND_TASKS_ENABLED` | Фоновые задачи (Celery) |

---

## API

Базовый префикс — `/api/v1`.

| Метод | Путь | Описание | Условие |
|---|---|---|---|
| GET | `/bootstrap` | Профиль и capabilities | всегда |
| GET | `/health` | Health-check (liveness) | всегда |
| — | `/auth/*` | Регистрация, вход, сброс пароля, пользователи | `AUTH_ENABLED` |
| — | `/user_flow/*` | Прикладные эндпоинты для любого вошедшего пользователя | `AUTH_ENABLED` |
| — | `/admin_flow/*` | Административные эндпоинты | `ADMIN_ENABLED` |
| POST/GET | `/file_flow/*` | Загрузка (только вошедшим) и скачивание файлов | `FILES_ENABLED` |

---

## Разработка

- **Модуль = папка.** Каждая возможность — пакет в `app/modules/<name>/` с функцией
  `register(app)`. Реестр `app/core/modules.py` импортирует пакет **только если он
  включён** и проверяет зависимости между модулями. Код модуля не импортируется
  снаружи, кроме других модулей, которые от него зависят (`requires`).
- **Удаление модуля из проекта:** удалить его папку, запись в `MODULES`
  (`app/core/modules.py`) и файл `requirements/<name>.txt`.
- **Новый домен приложения** — пакет `app/<domain>_flow/` по образцу `app/user_flow/`
  и запись в `MODULES`.
- **Добавление capability** (чек-лист):
  1. Флаг в `app/config.py` и `.env.example`.
  2. Пакет `app/modules/<name>/` с `register(app)` и запись в `MODULES`.
  3. Зависимости в `requirements/<name>.txt` (+ подключить в `standard.txt`).
  4. Поле в `Capabilities` (`app/core/capabilities.py`) и в `app/core/bootstrap.py`.
  5. Учесть флаг в UI/роутинге на фронтенде.
- **Команды:** `make install`, `make dev`, `make test`, `make lint`, `make format`
  (`make help` — список).
- **Миграции:** `alembic revision --autogenerate -m "<message>"`

---
