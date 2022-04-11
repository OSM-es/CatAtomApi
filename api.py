import os

from flask import Flask, redirect, request
from flask_restful import abort, Api, reqparse, Resource

from catatom2osm import config as cat_config
from catatom2osm import csvtools
from catatom2osm.exceptions import CatValueError

import user
from work import Work


WORK_DIR = os.environ['HOME']
app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
api = Api(app)

status_msg = {
    Work.Status.RUNNING: (
        409, "El municipio '{}' está siendo procesado"
    ),
    Work.Status.REVIEW: (
        405, "El municipio '{}' está pendiente de revisar"
    ),
    Work.Status.DONE: (
        405, "El municipio '{}' ya está procesado"
    ),
    Work.Status.AVAILABLE: (
        200, "El municipio '{}' no está procesado"
    ),
    Work.Status.ERROR: (
        200, "El municipio '{}' terminó con error"
    ),
}


class Login(Resource):
    def get(self):
        return user.get_authorize_url()


class Callback(Resource):
    def get(self):
        user_params = user.authorize()
        if user_params is None:
            abort(404, "Autorización denegada")
        return user_params


@app.route("/priv")
@user.auth.login_required
def private():
    return "private"


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
    def __init__(self):
        self.post_parser = reqparse.RequestParser()
        self.post_parser.add_argument('building', type=bool, default=True)
        self.post_parser.add_argument('address', type=bool, default=True)

    def get(self, mun_code):
        """Estado del proceso de un municipio."""
        linea = int(request.args.get("linea", 0))
        try:
            job = Work(mun_code)
        except CatValueError as e:
            abort(404, message=str(e))
        status = job.status()
        msg = status_msg[status][1].format(mun_code)
        log = ""
        if status != Work.Status.AVAILABLE: 
            log, linea = job.log(linea)
        return {
            "estado": str(status).split(".")[-1],
            "mensage": msg,
            "linea": linea,
            "log": log,
        }
    
    def post(self, mun_code):
        # TODO: recoger parámetro split
        # TODO: Eliminar barras de progreso
        """Procesa un municipio."""
        args = self.post_parser.parse_args()
        app.logger.info(args)
        # TODO: poner en catatom2osm check de building=address=False
        try:
            job = Work(mun_code, **args)
        except CatValueError as e:
            abort(404, message=str(e))
        status = job.status()
        if status not in [Work.Status.AVAILABLE, Work.Status.ERROR]:
            msg = status_msg[status][1].format(mun_code)
            abort(status_msg[status][0], message=msg)
        try:
            # TODO: crear dentro del directorio `mun_code` archivo user.txt
            # con el nombre de usuario para marcar el dueño
            pass  # job.start()
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            abort(500, message=msg)
        return {"mensage": _("Start processing '%s'") % mun_code}


    # TODO: put igual que post pero sin comprobar si existe
    
    # TODO: delete comprobar estado y borrar directorio si está terminado


api.add_resource(Login,'/login')
api.add_resource(Callback,'/authorized')
api.add_resource(Provinces,'/prov')
api.add_resource(Province,'/prov/<string:prov_code>')
api.add_resource(Job,'/job/<string:mun_code>')


@app.route("/")
def hello_world():
   return f"{cat_config.app_name} {cat_config.app_version} API"

