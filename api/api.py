from flask import Flask

from catatom2osm import config as cat_config

app = Flask(__name__)

@app.route("/")
def hello_world():
   return f"{cat_config.app_name} {cat_config.app_version} API"

