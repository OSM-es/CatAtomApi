import time
from authlib.jose import jwt
from authlib.jose.errors import JoseError
from authlib.integrations.flask_client import OAuth, OAuthError
from flask import abort, current_app, jsonify, redirect, session, url_for
from flask_httpauth import HTTPTokenAuth

auth = HTTPTokenAuth(scheme="Bearer")
oauth = OAuth()


def get_oauth():
    """Devuelve cliente OAuth2 configurado para OSM."""
    if not oauth.app:
        osm_url = current_app.config['OSM_URL']
        oauth.init_app(current_app)
        oauth.register(
            name='osm',
            access_token_url=osm_url + '/oauth2/token',
            authorize_url=osm_url + '/oauth2/authorize',
            api_base_url=osm_url + '/api/0.6/',
            client_kwargs={'scope': 'read_prefs'},
        )
    return oauth.osm

@auth.verify_token
def verify_token(token):
    """Verificador utilizado por auth.login_required"""
    oauth_token = session.get('oauth_token')
    return oauth_token == token

def login():
    """Redirige a la página de login de OSM."""
    redirect_uri = current_app.config.get('API_URL') + '/authorize'
    return get_oauth().authorize_redirect(redirect_uri)

def authorize():
    try:
        token = get_oauth().authorize_access_token(vertify=True)
    except OAuthError:
        abort(404, description="Autorización denegada")
    resp = get_oauth().get('user/details.json')
    resp.raise_for_status()
    data = resp.json() 
    session['user'] = {
        'osm_id': data['user']['id'],
        'username': data['user']['display_name'],
    }
    session['oauth_token'] = token
    return redirect(current_app.config.get('CLIENT_URL', '') + '/auth')

def logout():
    session.pop('user', None)
    session.pop('oauth_token', None)
    return redirect(current_app.config.get('CLIENT_URL', '') + '/home')

def user():
    user_info = session.get('user', None)
    if user_info:
        return jsonify(user_info)
    return jsonify({'error': 'No registrado'})
