# CatAtomApi
Diseño de una API web para interactuar con catatom2osm

## Registro
¿OAuth?

## Provincias
* url: /prov

### GET
Lista las provincias disponibles.

#### Petición
Sin parámetros

#### Respuesta
* 200 Success
  - {"provincias":[ {"cod_provincia":"02", "nombre":"Albacete"},...]}

## Municipios
* url: /prov/`prov code:99`

### GET
Lista los municipios disponibles.

#### Petición
Sin parámetros

#### Respuesta
* 200 Success
  - prov_code: Código de provincia
  - name: Nombre de la provincia
  - {"municipios":[ {"cod_municipio":"02001", "nombre":"Abengibre"},...]} Lista de códigos y municipios
* 400 Bad Request
  - msg: El Código Provincial '`prov code:99`' no es válido

## Divisiones
* url: /mun/`mun code:99999`

### GET
Lista las divisiones (distritos o barrios) disponibles.

#### Petición
Sin parámetros

#### Respuesta
* 200 Success
  - {"divisiones":[ {"osm_id":"1234567890", "nombre":"Nombre del distrito o barrio"},...]}
* 400 Bad Request
  - msg: El Código Provincial '`prov code:99`' no es válido
* 404 Not Found
  - msg: El código de municipio '`mun code:99999`' no existe
* 502 Bad Gateway
  - msg: No se puede acceder al servidor Overpass
* 504 Gateway Timeout
  - msg: Tiempo de respuesta agotado del servidor Overpass

## Procesar
* url: /job/`mun code`

### GET
Consulta el estado de un proceso.

#### Petición
Sin parámetros.

#### Respuesta
* 200 Success
  - status: string. "available", "running", "finished", "review"
  - user: Usuario que lanzó el proceso (si status=running).
  - log: string. Archivo de registro (si status=running).
  - url: string Página de resultados (si status=finished. Pagina de revisión de nombres de calles (si status=review)
* 400 Bad Request
  - msg: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - msg: Se requiere autenticación
* 404 Not Found
  - msg: El código de municipio '`mun code:99999`' no existe

### POST
Crea un proceso.

#### Petición
* building: boolean (por defecto true). Procesa edificios
* address: boolean (por defecto true). Procesa direcciones
* split: texto (por defecto none). Procesa una fracción de un municipio. Identificador (id) o nombre (name) del límite administrativo en OSM.

#### Respuesta
* 200 Success
  - msg: Se inicia el proceso de '`mun code:99999`', Se reanuda el proceso de '`mun code:9999`'
* 400 Bad Request
  - msg: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - msg: Se requiere autenticación
* 404 Not Found
  - msg: El código de municipio '`mun code:99999`' no existe
* 405 Method Not Allowed
  - msg: Se deben comprobar los nombres de las calles
  - url: string. Pagina de revisión de nombres de calles
* 409 Conflict
  - msg: El municipio '`mun code:99999`' está siendo procesado por `user`
* 502 Bad Gateway
  - msg: No se puede acceder al servidor Overpass
* 504 Gateway Timeout
  - msg: Tiempo de respuesta agotado del servidor Overpass

### PUT
Sobreescribe un proceso.

#### Petición
* building: boolean (por defecto true). Procesa edificios
* address: boolean (por defecto true). Procesa direcciones
* split: texto (por defecto none). Procesa una fracción de un municipio. Identificador (id) o nombre (name) del límite administrativo en OSM.

#### Respuesta
* 200 Success
  - msg: Se reinicia el proceso de 'mun code:9999>
* 400 Bad Request
  - msg: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - msg: Se requiere autenticación
* 403 Forbidden
  - msg: El proceso del municipio '`mun code:99999`' corresponde a `user`
* 404 Not Found
  - msg: El código de municipio '`mun code:99999`' no existe
* 409 Conflict
  - msg: El municipio '`mun code:99999`' está siendo procesado por `user`
* 502 Bad Gateway
  - msg: No se puede acceder al servidor Overpass
* 504 Gateway Timeout
  - msg: Tiempo de respuesta agotado del servidor Overpass

### DELETE
Elimina un proceso.

#### Petición
Sin parámetros.

#### Respuesta
* 200 Success
  - msg: Se ha eliminado el municipio '`mun code:99999`'
* 400 Bad Request
  - msg: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - msg: Se requiere autenticación
* 403 Forbidden
  - msg: El proceso del municipio '`mun code:99999`' corresponde a `user`
* 404 Not Found
  - msg: El código de municipio '`mun code:99999`' no existe
* 409 Conflict
  - msg: El municipio '`mun code:99999`' está siendo procesado por `user`
