import argparse
import atexit
import os

from flask import Flask
from flask_restful import abort, Api, Resource

from catatom2osm import config as cat_config
from catatom2osm import csvtools
from catatom2osm.app import CatAtom2Osm, QgsSingleton

WORK_DIR = "/catastro"
app = Flask(__name__)
api = Api(app)
qgs = QgsSingleton()        


def shutdown():
    qgs.exitQgis()
    
atexit.register(shutdown)


default_options = dict(
    address=True,
    building=True,
    comment=False,
    config_file=False,
    download=False,
    generate_config=False,
    manual=False,
    zoning=False,
    list='',
    split=None,
    parcel=[],
    log_level='INFO',
)


class Provinces(Resource):
    def get(self):
        """Devuelve lista de provincias."""
        data={
            "provinces": cat_config.prov_codes,
        }
        return data
  

class Province(Resource):
    def get(self, prov_code):
        """Devuelve lista de municipios"""
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


class Job(Resource):
    def post(self, mun_code):
        """Procesa un municipio."""
        fn = os.path.join(cat_config.app_path, "municipalities.csv")
        result = csvtools.get_key(fn, mun_code)
        if not result:
            msg = _("Municipality code '%s' don't exists") % mun_code
            abort(404, message=msg)
        os.chdir(WORK_DIR)
        if os.path.exists(mun_code):
            msg = f"El municipio '{mun_code}' está siendo procesado"
            abort(409, message=msg)
        os.mkdir(mun_code)
        options = argparse.Namespace(**default_options)
        options.path = [mun_code]
        options.args = mun_code
        CatAtom2Osm.create_and_run(mun_code, options)
        return {"msg": _("Start processing '%s'").format(mun_code)}


api.add_resource(Provinces,'/prov')
api.add_resource(Province,'/prov/<string:prov_code>')
api.add_resource(Job,'/job/<string:mun_code>')


@app.route("/")
def hello_world():
   return f"{cat_config.app_name} {cat_config.app_version} API"
 
