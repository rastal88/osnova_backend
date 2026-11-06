COMPOSE ?= docker compose
PYTHON ?= venv/bin/python

BASE := -f docker-compose.yml
DATA := -f docker-compose.yml -f docker-compose.datastores.yml

.PHONY: help install dev test lint format openapi up-minimal up-standard up-scalable down down-volumes logs ps build

help:  ## Show available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:  ## Create venv and install all modules + dev tools
	python3.13 -m venv venv
	$(PYTHON) -m pip install -r requirements/dev.txt

dev:  ## Run the API locally with auto-reload
	$(PYTHON) run.py

test:  ## Run tests
	$(PYTHON) -m pytest

lint:  ## Check code style
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:  ## Fix code style
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

openapi:  ## Write openapi.json for the frontend client
	$(PYTHON) -m scripts.openapi

up-minimal:  ## Docker: backend + frontend, no datastores
	$(COMPOSE) $(BASE) --profile minimal up --build -d

up-standard:  ## Docker: + PostgreSQL + Redis
	$(COMPOSE) $(DATA) --profile standard up --build -d

up-scalable:  ## Docker: standard with several backend replicas
	$(COMPOSE) $(DATA) --profile scalable up --build -d --scale backend=3

down:  ## Stop containers
	$(COMPOSE) $(DATA) down

down-volumes:  ## Stop containers and delete data volumes
	$(COMPOSE) $(DATA) down -v

logs:  ## Follow logs
	$(COMPOSE) $(DATA) logs -f

ps:  ## List containers
	$(COMPOSE) $(DATA) ps

build:  ## Build all images
	$(COMPOSE) $(DATA) --profile scalable build
