import os

import oauthlib.oauth1
from dotenv import load_dotenv

# Para configuración de producción crea el archivo api.env con las variables:
# FLASK_SECRET_KEY = "Genera una clave aleatoria para securizar las sesiones"
# OSM_CLIENT_ID = "Registra la aplicación en https://osm.org/user/Javier Sanchez/oauth_clients"
# OSM_CLIENT_SECRET = 

load_dotenv("api.env")


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", None)
    OSM_CLIENT_ID = os.getenv("OSM_CLIENT_ID", "")
    OSM_CLIENT_SECRET = os.getenv("OSM_CLIENT_SECRET", "")
    SESSION_COOKIE_SAMESITE = "Strict"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 Mb

class DevelopmentConfig(Config):
    CLIENT_URL = "http://localhost:8080"

class ProductionConfig(Config):
    API_URL = "https://cat.cartobase.es/api"
    CLIENT_URL = "https://cat.cartobase.es"


def get_config(mode="development"):
    config_class = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
    }
    return config_class[mode]()
