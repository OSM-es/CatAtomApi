import oauthlib.oauth1


OSM_SERVER_URL = "https://www.openstreetmap.org"
OSM_OAUTH_SETTINGS = {
    "base_url": f"{OSM_SERVER_URL}/api/0.6/",
    "consumer_key": "NQAJ7xM4DZdeO8HU6ltsz7TBxhkSAEKvTSXrGC1T",
    "consumer_secret": "LFMPS1FnZPyLfPg0WrOFbleGefwEKR4VWC4LMGnp",
    "request_token_url": f"{OSM_SERVER_URL}/oauth/request_token",
    "access_token_url": f"{OSM_SERVER_URL}/oauth/access_token",
    "authorize_url": f"{OSM_SERVER_URL}/oauth/authorize",
    "signature_method": oauthlib.oauth1.SIGNATURE_PLAINTEXT,
}
