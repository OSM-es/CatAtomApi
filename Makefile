WEB_USER = www-data
WEB_GROUP = www-data
WORK_DIR = /var/catastro

.PHONY: help
help:  ## Show this help
	@echo "Please use \`make <target>\` where <target> is one of"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install:
	@if [ ! -d "$(WORK_DIR)" ]; then \
	    mkdir -p "$(WORK_DIR)" && \
	    chmod 775 "$(WORK_DIR)" && \
	    chown -R $(WEB_USER):$(WEB_GROUP) "$(WORK_DIR)"; \
	fi

.PHONY: catatom2osm
catatom2osm: install  ## Add catato2osm submodule
    @git submodule add -f https://github.com/OSM-es/CatAtom2Osm catatom2osm

.PHONY: submodules
submodules: catatom2osm  ## Update submodules
	@git submodule update --init --recursive
	@git submodule update --remote --merge

.PHONY: build
build: submodules  ## Build docker image
	@docker build --build-arg user=www-data --build-arg group=www-data --build-arg uid=$(id -u www-data) --build-arg gid=$(id -g www-data) -t catatom2osm4api catatom2osm
	@docker compose build
	
.PHONY: up
up: build  ## Start docker container as a service
	@docker compose up -d

.PHONY: logs
logs:  ## Show container logs
	@docker compose logs -f web

.PHONY: down
down:  ## Stop service
	@docker compose down

.PHONY: debug
debug:  ## Run docker container in debug mode
	@docker compose run --rm -p 5001:5001 -e FLASK_ENV=development -e FLASK_PORT=5001 -e RELOAD="--reload" -v $(PWD):/opt/CatAtomAPI web
