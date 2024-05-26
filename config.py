import os

import oauthlib.oauth1
from dotenv import load_dotenv

# Registra la aplicación en https://www.openstreetmap.org/user/<username>/oauth_clients/new
# En "URL de la aplicación principal" debes poner: http://localhost:8080
# y marcar la opción "leer sus preferencias de usuario"
# Crea el archivo api.env con las variables:
# FLASK_SECRET_KEY = "Genera una clave aleatoria para securizar las sesiones"
# OSM_CLIENT_ID = "Clave de Consumidor"
# OSM_CLIENT_SECRET = "Secreto de Consumidor"

load_dotenv("api.env")
load_dotenv("api.prod.env")


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", None)
    OSM_CLIENT_ID = os.getenv("OSM_CLIENT_ID", "")
    OSM_CLIENT_SECRET = os.getenv("OSM_CLIENT_SECRET", "")
    OSM_URL = os.getenv('OSM_URL', 'https://www.openstreetmap.org')
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 Mb
    API_URL = os.getenv("API_URL", "http://127.0.0.1:5000")
    CLIENT_URL = os.getenv("CLIENT_URL", "http://127.0.0.1:8080")
