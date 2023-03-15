# CatAtomApi
API web para interactuar con catatom2osm

## Requisitos
Docker https://www.docker.com/get-started

En linux añade tu usuario al grupo docker
https://docs.docker.com/engine/install/linux-postinstall/

## Instalación

    make build
    docker network create catatom
    sudo mkdir /var/catastro
    sudo chmod www-data:www-data /var/catastro

## Uso

Levantar el servicio

    make up

Para otros usos ver el Makefile

    make

## Documentación
Ver [doc_api.md](doc_api.md)

## Producción
Crear api.env siguiendo instrucciones de config.py
