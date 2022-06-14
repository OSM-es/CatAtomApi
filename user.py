import requests
from xml.etree import ElementTree as ET 

from authlib.integrations.flask_client import OAuth, OAuthError
from flask import current_app, g, request, session, url_for
from flask_httpauth import HTTPTokenAuth
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

OSM_SERVER_URL = "https://www.openstreetmap.org"

auth = HTTPTokenAuth(scheme="Token")
oauth = OAuth(current_app)
osm = oauth.register('osm',
    api_base_url=f"{OSM_SERVER_URL}/api/0.6/",
    request_token_url=f"{OSM_SERVER_URL}/oauth/request_token",
    access_token_url=f"{OSM_SERVER_URL}/oauth/access_token",
    authorize_url=f"{OSM_SERVER_URL}/oauth/authorize",
)


@auth.verify_token
def verify_token(token):
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    try:
        g.user_data = serializer.loads(token, max_age=864000)
    except (SignatureExpired, BadSignature):
        return False
    return g.user_data

def get_authorize_url(callback_url = None):
    api_url = current_app.config.get("API_URL", request.host_url)
    callback = callback_url or (api_url + url_for("callback"))
    return osm.authorize_redirect(callback)

def authorize():
    try:
        token = osm.authorize_access_token()
    except OAuthError:
        return None
    if token is None:
        return None
    session["osm_oauth"] = token
    response = osm.get("user/details")
    root = ET.fromstring(response.content)
    user = root.find("user")
    osm_id = user.get("id")
    username = user.get("display_name")
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    data = {
        "osm_id": osm_id,
        "username": username,
    }
    session_token = serializer.dumps(data)
    data["session_token"] = session_token
    return data

