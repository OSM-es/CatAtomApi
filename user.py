import requests

from flask import current_app, request, session, url_for
from flask_httpauth import HTTPTokenAuth
from flask_oauthlib.client import OAuth
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.urls import url_quote

auth = HTTPTokenAuth(scheme="Token")
oauth = OAuth()
osm = oauth.remote_app("osm", app_key="OSM_OAUTH_SETTINGS")


@auth.verify_token
def verify_token(token):
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    try:
        user_id = serializer.loads(token, max_age=3600)
    except (SignatureExpired, BadSignature):
        return False
    return user_id


@osm.tokengetter
def get_oauth_token():
    if "osm_oauth" in session:
        resp = session["osm_oauth"]
        return resp["oauth_token"], resp["oauth_token_secret"]


def get_authorize_url():
    # TODO: next
    callback = url_for("callback")
    token, secret = osm.generate_request_token(callback)
    url = f"{osm.expand_url(osm.authorize_url)}?oauth_token={url_quote(token)}"
    return {
        "oauth_token": token,
        "oauth_token_secret": secret,
        "auth_url": url,
    }


def authorize():
    resp = osm.authorized_response()
    if resp is None:
        return None
    session["osm_oauth"] = resp
    response = osm.request("user/details")
    user = response.data.find("user")
    osm_id = int(user.attrib["id"])
    username = user.attrib["display_name"]
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    session_token = serializer.dumps(osm_id)
    session["osm_oauthtok"] = (
        request.args.get("oauth_token"),
        request.args.get("oauth_token_secret"),
    )
    return {
        "username": username,
        "osm_id": osm_id,
        "session_token": session_token,
        "session": resp,
    }

