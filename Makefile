COMPOSE ?= docker compose

BASE := -f docker-compose.yml
DATA := -f docker-compose.yml -f docker-compose.datastores.yml

.PHONY: up-minimal up-standard up-scalable down down-volumes logs ps build

up-minimal:
	$(COMPOSE) $(BASE) --profile minimal up --build -d

up-standard:
	$(COMPOSE) $(DATA) --profile standard up --build -d

up-scalable:
	$(COMPOSE) $(DATA) --profile scalable up --build -d

down:
	$(COMPOSE) $(DATA) down

down-volumes:
	$(COMPOSE) $(DATA) down -v

logs:
	$(COMPOSE) $(DATA) logs -f

ps:
	$(COMPOSE) $(DATA) ps

build:
	$(COMPOSE) $(DATA) --profile scalable build
