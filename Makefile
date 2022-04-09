CAT_USER = catastro
GROUP = catastro
CAT_HOME = /home/catastro
UID = 900
GID = 900

.PHONY: help
help:  ## Show this help
	@echo "Please use \`make <target>\` where <target> is one of"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: $(CAT_HOME)
$(CAT_HOME):
	@mkdir -p "$(CAT_HOME)" && chown $(UID):$(GID) "$(CAT_HOME)"
	@addgroup --gid $(GID) $(GROUP)
	@useradd -d "$(CAT_HOME)" -u $(UID) -g $(GROUP) -s /usr/sbin/nologin $(CAT_USER)
	@usermod -a -G www-data $(CAT_USER)
	@usermod -a -G docker $(CAT_USER)

.PHONY: catatom2osm
catatom2osm: $(CAT_HOME)  ## Add catato2osm submodule
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
	@docker run -d --name catatomapi -p 5000:5000 -v /var/catastro:/catastro catatomapi

.PHONY: logs
logs:  ## Show container logs
	@docker logs catatomapi -f

.PHONY: debug
debug:  ## Run docker container in debug mode
	@docker run -it --rm -p 5001:5001 -e FLASK_ENV=development -e FLASK_PORT=5001 -v $(PWD):/opt/CatAtomAPI -v /var/catastro:/catastro catatomapi

