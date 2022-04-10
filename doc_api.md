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
  - cod_provincia: Código de provincia
  - nombre: Nombre de la provincia
  - {"municipios":[ {"cod_municipio":"02001", "nombre":"Abengibre"},...]} Lista de códigos y municipios
* 400 Bad Request
  - message: El Código Provincial '`prov code:99`' no es válido

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
  - message: El Código Provincial '`prov code:99`' no es válido
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe
* 502 Bad Gateway
  - message: No se puede acceder al servidor Overpass
* 504 Gateway Timeout
  - message: Tiempo de respuesta agotado del servidor Overpass

## Procesar
* url: /job/`mun code`

### GET
Consulta el estado de un proceso.

#### Petición
Sin parámetros.

#### Respuesta
* 200 Success
  - estado: string. "disponible", "ejecutando", "terminado", "revisar"
  - usuario: Usuario que lanzó el proceso (si estado=disponible).
  - log: string. Archivo de registro (si status=ejecutando).
  - url: string Página de resultados (si status=terminado. Pagina de revisión de nombres de calles (si estado=revisar)
* 400 Bad Request
  - message: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - message: Se requiere autenticación
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe

### POST
Crea un proceso.

#### Petición
* building: boolean (por defecto true). Procesa edificios
* address: boolean (por defecto true). Procesa direcciones
* split: texto (por defecto none). Procesa una fracción de un municipio. Identificador (id) o nombre (name) del límite administrativo en OSM.

#### Respuesta
* 200 Success
  - message: Se inicia el proceso de '`mun code:99999`', Se reanuda el proceso de '`mun code:9999`'
* 400 Bad Request
  - message: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - message: Se requiere autenticación
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe
* 405 Method Not Allowed
  - message: Se deben comprobar los nombres de las calles
  - url: string. Pagina de revisión de nombres de calles
* 409 Conflict
  - message: El municipio '`mun code:99999`' está siendo procesado por `user`
* 502 Bad Gateway
  - message: No se puede acceder al servidor Overpass
* 504 Gateway Timeout
  - message: Tiempo de respuesta agotado del servidor Overpass

### PUT
Sobreescribe un proceso.

#### Petición
* building: boolean (por defecto true). Procesa edificios
* address: boolean (por defecto true). Procesa direcciones
* split: texto (por defecto none). Procesa una fracción de un municipio. Identificador (id) o nombre (name) del límite administrativo en OSM.

#### Respuesta
* 200 Success
  - message: Se reinicia el proceso de 'mun code:9999>
* 400 Bad Request
  - message: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - message: Se requiere autenticación
* 403 Forbidden
  - message: El proceso del municipio '`mun code:99999`' corresponde a `user`
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe
* 409 Conflict
  - message: El municipio '`mun code:99999`' está siendo procesado por `user`
* 502 Bad Gateway
  - message: No se puede acceder al servidor Overpass
* 504 Gateway Timeout
  - message: Tiempo de respuesta agotado del servidor Overpass

### DELETE
Elimina un proceso.

#### Petición
Sin parámetros.

#### Respuesta
* 200 Success
  - message: Se ha eliminado el municipio '`mun code:99999`'
* 400 Bad Request
  - message: El Código Provincial '`prov code:99`' no es válido
* 401 Unauthorized
  - message: Se requiere autenticación
* 403 Forbidden
  - message: El proceso del municipio '`mun code:99999`' corresponde a `user`
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe
* 409 Conflict
  - message: El municipio '`mun code:99999`' está siendo procesado por `user`
