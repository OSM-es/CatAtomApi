# CatAtomApi
Diseño de una API web para interactuar con catatom2osm

## Registro
* url: /login

### GET
Redirige usuarios a OSM OAuth

#### Petición
* next: Url de regreso tras autenticar

#### Respuesta
* 200 Success
  - oauth_token: token
  - oauth_token_secret: secret
  - auth_url: url

## Retorno de registro
* url: /callback

### GET
Registra al usuario tras autenticación OAuth

#### Petición
* next: Url de regreso tras autenticar

#### Respuesta
* 200 Success
  - username: nombre de usuario
  - osm_id: identificador OSM
  - session_token: token de autenticación (debe pasarse en la cabecera)
    + "Authorization: Token <session_token>"

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
  - municipios:[ {"cod_municipio":"02001", "nombre":"Abengibre"},...] Lista de códigos y municipios
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
  - "divisiones": [{"osm_id":"1234567890", "nombre":"Nombre del distrito o barrio"},...]
* 400 Bad Request
  - message: El código de municipio '`mun code:99999`' no existe
* 502 Bad Gateway
  - message: No se puede acceder al servidor Overpass
* 504 Gateway Timeout
  - message: Tiempo de respuesta agotado del servidor Overpass

## Procesar
* url: /job/`mun code`           Código de municipio (5 dígitos).
       /job/`mun code`/`split`   Identificador OSM del límite administrativo de un distrito o barrio

### GET
Consulta el estado de un proceso.

#### Petición
* linea: desde que linea devolver el registro.

#### Respuesta
* 200 Success
  - cod_municipio: Código de municipio (5 dígitos).
  - cod_division: Identificador OSM del límite administrativo de un distrito o barrio
  - propietario: {osm_id, username} Usuario que ha iniciado el proceso
  - estado: "AVAILABLE", "RUNNING", "REVIEW", "FIXME, "DONE"
  - mensaje: Mensaje de estado extendido 
  - usuario: Usuario que lanzó el proceso.
  - log: Líneas del archivo de registro.
  - linea: número de líneas del archivo de registro.
  - informe: Líneas del archivo de informe.
  - revisar: Lista de archivos de tareas que hay que revisar.
* 401 Unauthorized
  - message: Se requiere autenticación
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe

### POST
Crea un proceso.

#### Petición
* building: boolean (por defecto true). Procesa edificios
* address: boolean (por defecto true). Procesa direcciones
* idioma: es_ES / ca_ES / gl_ES

#### Respuesta
* 200 Success
  - cod_municipio: Código de municipio (5 dígitos).
  - cod_division: Identificador OSM del límite administrativo de un distrito o barrio
  - propietario: {osm_id, username} Usuario que ha iniciado el proceso
  - mensaje: Procesando...
* 401 Unauthorized
  - message: Se requiere autenticación
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe
* 405 Method Not Allowed
  - message: Pendiente de revisar direcciones / problemas
* 409 Conflict
  - message: Proceso bloqueado por `user`

### PUT
Actualiza los archivos de tareas de un proceso.

#### Petición
* files["file"]: archivo a subir

#### Respuesta
* 200 Success
* 400 Bad request
  - message: Sólo archivos de tareas existentes
             No es un archivo gzip válido

### DELETE
Elimina un proceso.

#### Petición
Sin parámetros.

#### Respuesta
* 200 Success
  - cod_municipio: Código de municipio (5 dígitos).
  - cod_division: Identificador OSM del límite administrativo de un distrito o barrio
  - propietario: {osm_id, username} Usuario que ha iniciado el proceso
  - mensaje: Proceso desbloqueado
* 401 Unauthorized
  - message: Se requiere autenticación
* 404 Not Found
  - message: El código de municipio '`mun code:99999`' no existe
* 409 Conflict
  - message: Proceso bloqueado por `user`
* 410 Gone
  - message: No se pudo eliminar
