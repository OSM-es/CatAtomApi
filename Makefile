.PHONY: help
help:  ## Show this help
	@echo "Please use \`make <target>\` where <target> is one of"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: submodules
submodules:  ## Update submodules
	@git submodule update --init

.PHONY: build
build:  ## Build docker image
	@make -C catatom2osm build
	@docker build -t catatomapi .
	
.PHONY: run
run:  ## Run docker container
	@docker run -d --name catatomapi -p 5000:5000 catatomapi

.PHONY: logs
logs:  ## Show container logs
	@docker logs catatomapi -f

