# CatAtomApi
API web para interactuar con catatom2osm

## Requisitos
Docker https://www.docker.com/get-started

En linux añade tu usuario al grupo docker
https://docs.docker.com/engine/install/linux-postinstall/

## Instalación

    sudo make install
    make build
    docker network create catatom

Crear api.env siguiendo las instrucciones de config.py

## Desarrollo

Servidor de desarrollo

    make debug

Queda disponible en http://localhost:5001

## Producción

Siguiendo las instrucciones de config.py registrar https://cat.cartobase.es
y añadir las claves a api.env
Levantar el servicio con

    make up

Queda disponible en http://localhost:5000

Para otros usos ver el Makefile

    make

## Documentación
Ver [doc_api.md](doc_api.md)
