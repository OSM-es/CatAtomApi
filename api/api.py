import argparse
import atexit
import os

from flask import Flask
from flask_restful import abort, Api, Resource

from catatom2osm import config as cat_config
from catatom2osm import csvtools
# TODO: depurar ResourceWarning: unclosed <socket.socket
from catatom2osm.app import CatAtom2Osm, QgsSingleton

WORK_DIR = "/catastro"
app = Flask(__name__)
api = Api(app)

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


def shutdown():
    qgs.exitQgis()

if app.config.get("ENV", "") == "production":
    qgs = QgsSingleton()        
    atexit.register(shutdown)


# TODO: login


class Provinces(Resource):
    def get(self):
        """Devuelve lista de provincias."""
        provinces = [
            {"cod_provincia": cod_provincia, "nombre": nombre}
            for cod_provincia, nombre in cat_config.prov_codes.items()
        ]
        data = {
            "provincias": provinces,
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
            {"cod_municipio": mun[0], "nombre": mun[2]}
            for mun in csvtools.startswith(fn, prov_code)
        ]
        data={
            "cod_provincia": prov_code,
            "nombre": office, 
            "municipios": municipalities,
        }
        return data


# TODO: divisiones
# igual que catato2osm.boundary. Crear función get_districts alli
# llamada desde list_districts para imprimir


class Job(Resource):
    # TODO: get
    #  crear funcion para comprobar estado
    #  si existe directorio mun_code
    #    "review" si existe highway_names.csv
    #    "finished" si existe mun_code/tasks
    #    "running" si no
    #  "available" si no existe directorio mun_code
    
    def post(self, mun_code):
        # TODO: recoger parámetros buiding, address, split
        # TODO: meter en try y tratar excepciones
        # TODO: errores de overpass
        # TODO: ajustar un log separado para cada trabajo
        """Procesa un municipio."""
        fn = os.path.join(cat_config.app_path, "municipalities.csv")
        result = csvtools.get_key(fn, mun_code)
        if not result:
            msg = _("Municipality code '%s' don't exists") % mun_code
            abort(404, message=msg)
        os.chdir(WORK_DIR)
        prov_code = mun_code[0:2]
        if prov_code not in cat_config.prov_codes.keys():
            msg = _("Province code '%s' is not valid") % prov_code
            abort(404, message=msg)
        if os.path.exists(mun_code):
            # TODO: comprobar estado y diferenciar el mensaje
            msg = f"El municipio '{mun_code}' está siendo procesado"
            abort(409, message=msg)
        os.mkdir(mun_code)
        # TODO: crear dentro del directorio `mun_code` archivo user.txt
        # con el nombre de usuario para marcar el dueño
        options = argparse.Namespace(**default_options)
        options.path = [mun_code]
        options.args = mun_code
        log = cat_config.setup_logger(log_path=mun_code)
        CatAtom2Osm.create_and_run(mun_code, options)
        return {"mensage": _("Start processing '%s'").format(mun_code)}


    # TODO: put igual que get pero sin comprobar si existe
    
    # TODO: delete comprobar estado y borrar directorio si está terminado


api.add_resource(Provinces,'/prov')
api.add_resource(Province,'/prov/<string:prov_code>')
api.add_resource(Job,'/job/<string:mun_code>')


@app.route("/")
def hello_world():
   return f"{cat_config.app_name} {cat_config.app_version} API"

