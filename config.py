import os

import oauthlib.oauth1
from dotenv import load_dotenv


load_dotenv("api.env")
    
OSM_SERVER_URL = "https://www.openstreetmap.org"
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", None)
OSM_OAUTH_SETTINGS = {
    "base_url": f"{OSM_SERVER_URL}/api/0.6/",
    "consumer_key": os.getenv("OSM_CONSUMER_KEY", ""),
    "consumer_secret": os.getenv("OSM_CONSUMER_SECRET", ""),
    "request_token_url": f"{OSM_SERVER_URL}/oauth/request_token",
    "access_token_url": f"{OSM_SERVER_URL}/oauth/access_token",
    "authorize_url": f"{OSM_SERVER_URL}/oauth/authorize",
    "signature_method": oauthlib.oauth1.SIGNATURE_PLAINTEXT,
}
