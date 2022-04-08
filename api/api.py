import os

from flask import Flask
from flask_restful import abort, Api, Resource

from catatom2osm import config as cat_config
from catatom2osm import csvtools

app =   Flask(__name__)
api =   Api(app)


class Provinces(Resource):
    def get(self):
        data={
            "provinces": cat_config.prov_codes,
        }
        return data
  

class Province(Resource):
    def get(self, prov_code):
        fn = os.path.join(cat_config.app_path, "municipalities.csv")
        if prov_code not in cat_config.prov_codes.keys():
            msg = _("Province code '%s' is not valid") % prov_code
            abort(404, message=msg)
        office = cat_config.prov_codes[prov_code]
        municipalities = [
            {"mun_code": mun[0], "name": mun[2]}
            for mun in csvtools.startswith(fn, prov_code)
        ]
        data={
            "prov_code": prov_code,
            "name": office, 
            "municipalities": municipalities,
        }
        return data


api.add_resource(Provinces,'/prov')
api.add_resource(Province,'/prov/<string:prov_code>')


@app.route("/")
def hello_world():
   return f"{cat_config.app_name} {cat_config.app_version} API"
 
