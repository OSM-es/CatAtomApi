WEB_USER = www-data
WEB_GROUP = www-data
WEB_DIR = /var/www/html/results

.PHONY: help
help:  ## Show this help
	@echo "Please use \`make <target>\` where <target> is one of"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install:
	@if [ ! -d "$(WEB_DIR)" ]; then \
	    mkdir -p "$(WEB_DIR)" && \
	    chmod 775 "$(WEB_DIR)" && \
	    chown -R $(WEB_USER):$(WEB_GROUP) "$(WEB_DIR)"; \
	fi

.PHONY: catatom2osm
catatom2osm: install  ## Add catato2osm submodule
    @git submodule add -f https://github.com/OSM-es/CatAtom2Osm catatom2osm

.PHONY: submodules
submodules: catatom2osm  ## Update submodules
	@git submodule update --init

.PHONY: build
build: submodules  ## Build docker image
	@make -C catatom2osm build
	@docker build -t catatomapi .
	
.PHONY: up
up: build  ## Start docker container as a service
	@docker-compose up -d

.PHONY: logs
logs:  ## Show container logs
	@docker-compose logs -f web

.PHONY: down
down: build  ## Stop service
	@docker-compose down

.PHONY: debug
debug:  ## Run docker container in debug mode
	@docker-compose run --rm -p 5001:5001 -e FLASK_ENV=development -e FLASK_PORT=5001 -v $(PWD):/opt/CatAtomAPI web

