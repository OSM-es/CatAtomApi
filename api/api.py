from flask import Flask
from flask_restful import Api, Resource

from catatom2osm import config as cat_config

app =   Flask(__name__)
api =   Api(app)


class Provinces(Resource):
    def get(self):
        data={
            "provinces": [],
        }
        return data
  

class Province(Resource):
    def get(self, prov_code):
        data={
            "prov_code": prov_code, 
            "municipalities": []
        }
        return data


api.add_resource(Provinces,'/prov')
api.add_resource(Province,'/prov/<string:prov_code>')


@app.route("/")
def hello_world():
   return f"{cat_config.app_name} {cat_config.app_version} API"
 
