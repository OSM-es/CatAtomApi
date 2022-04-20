import os

import oauthlib.oauth1
from dotenv import load_dotenv


load_dotenv("api.env")
# Para configuración de producción crea el archivo api.env con las variables:
# FLASK_SECRET_KEY = "Genera una clave aleatoria para securizar las sesiones"
# API_URL = "https://cat.cartobase.es/api"
# OSM_CLIENT_ID = "Registra la aplicación en https://osm.org/user/Javier Sanchez/oauth_clients"
# OSM_CLIENT_SECRET = 
# Ca2O_SHOW_PROGRESS_BARS = False
    
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", None)
if "API_URL" in os.environ:
    API_URL = os.getenv("API_URL")
OSM_CLIENT_ID = os.getenv("OSM_CLIENT_ID", "")
OSM_CLIENT_SECRET = os.getenv("OSM_CLIENT_SECRET", "")
SESSION_COOKIE_SAMESITE = "Strict"
