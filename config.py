import os

import oauthlib.oauth1
from dotenv import load_dotenv


load_dotenv("api.env")
    
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", None)
if "API_URL" in os.environ:
    API_URL = os.getenv("API_URL")
OSM_CLIENT_ID = os.getenv("OSM_CONSUMER_KEY", "")
OSM_CLIENT_SECRET = os.getenv("OSM_CONSUMER_SECRET", "")
SESSION_COOKIE_SAMESITE = "Strict"
