.PHONY: help
help:  ## Show this help
	@echo "Please use \`make <target>\` where <target> is one of"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: catatom2osm
catatom2osm:  ## Add catato2osm submodule
    @git submodule add -f https://github.com/OSM-es/CatAtom2Osm catatom2osm

.PHONY: submodules
submodules: catatom2osm  ## Update submodules
	@git submodule update --init

.PHONY: build
build: submodules  ## Build docker image
	@make -C catatom2osm build
	@docker build -t catatomapi .
	
.PHONY: run
run: build  ## Run docker container
	@docker run -d --name catatomapi -p 5000:5000 catatomapi

.PHONY: logs
logs:  ## Show container logs
	@docker logs catatomapi -f

