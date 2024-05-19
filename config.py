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


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", None)
    OSM_CLIENT_ID = os.getenv("OSM_CLIENT_ID", "")
    OSM_CLIENT_SECRET = os.getenv("OSM_CLIENT_SECRET", "")
    OSM_URL = os.getenv('OSM_URL', 'https://www.openstreetmap.org')
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 Mb

class DevelopmentConfig(Config):
    CLIENT_URL = os.getenv("CLIENT_URL", "http://127.0.0.1:8080")

class ProductionConfig(Config):
    API_URL = "https://cat.cartobase.es/api"
    CLIENT_URL = "https://cat.cartobase.es"


def get_config(mode="development"):
    config_class = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
    }
    return config_class[mode]()
