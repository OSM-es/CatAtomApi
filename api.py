import os

from flask import Flask, redirect, request
from flask_restful import abort, Api, reqparse, Resource

from catatom2osm import config as cat_config
from catatom2osm import csvtools
from catatom2osm.boundary import get_districts
from catatom2osm.exceptions import CatValueError

import user
from work import Work


WORK_DIR = os.environ['HOME']
app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
api = Api(app)

status_msg = {
    Work.Status.RUNNING: (
        409, "Procesando..."
    ),
    Work.Status.REVIEW: (
        405, "Pendiente de revisar direcciones"
    ),
    Work.Status.FIXME: (
        405, "Pendiente de revisar problemas"
    ),
    Work.Status.DONE: (
        405, "Proceso finalizado"
    ),
    Work.Status.AVAILABLE: (
        200, "No procesado"
    ),
    Work.Status.ERROR: (
        200, "Terminó con error"
    ),
}


class Login(Resource):
    def get(self):
        callback = request.args.get('callback')
        app.logger.info(callback)
        return user.get_authorize_url(callback)


class Authorize(Resource):
    def get(self):
        user_params = user.authorize()
        if user_params is None:
            abort(404, message="Autorización denegada")
        return user_params


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
        return {
            "cod_provincia": prov_code,
            "nombre": office, 
            "municipios": municipalities,
        }


class Municipality(Resource):
    def get(self, mun_code):
        """Devuelve lista de distritos/barrios"""
        try:
            job = Work(mun_code)
        except CatValueError as e:
            abort(404, message=str(e))
        divisiones = [
            {
                "osm_id": district[1],
                "nombre": f"{'  ' if district[0] else ''}{district[2]} {district[3]}",
            } 
            for district in get_districts(mun_code)
        ]
        return {
            "cod_municipio": mun_code,
            "divisiones": divisiones,
        }


class Job(Resource):
    def __init__(self):
        self.post_parser = reqparse.RequestParser()
        self.post_parser.add_argument('building', type=bool, default=True)
        self.post_parser.add_argument('address', type=bool, default=True)

    def get(self, mun_code, split=None):
        """Estado del proceso de un municipio."""
        linea = int(request.args.get("linea", 0))
        app.logger.info(split)
        try:
            job = Work(mun_code, split=split)
        except CatValueError as e:
            abort(404, message=str(e))
        status = job.status()
        msg = status_msg[status][1]
        log = ""
        if status != Work.Status.AVAILABLE: 
            log, linea = job.log(linea)
        return {
            "estado": str(status).split(".")[-1],
            "mensaje": msg,
            "linea": linea,
            "log": log,
            "informe": job.report(),
            "report": job.report_json(),
            "revisar": job.review(),
        }
    
    @user.auth.login_required
    def post(self, mun_code, split=None):
        """Procesa un municipio."""
        app.logger.info(split)
        args = self.post_parser.parse_args()
        token = request.headers.get("Authorization", "")[6:]
        user_data = user.verify_token(token)
        try:
            job = Work(mun_code, user_data, split, **args)
        except CatValueError as e:
            abort(404, message=str(e))
        status = job.status()
        if status not in [Work.Status.AVAILABLE, Work.Status.ERROR]:
            msg = status_msg[status][1].format(mun_code)
            abort(status_msg[status][0], message=msg)
        try:
            job.start()
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            abort(500, message=msg)
        return {"mensaje": _("Start processing '%s'") % mun_code}


    # TODO: put igual que post pero sin comprobar si existe
    
    # TODO: delete comprobar estado y borrar directorio si está terminado


api.add_resource(Login,'/login')
api.add_resource(Authorize,'/authorize')
api.add_resource(Provinces,'/prov')
api.add_resource(Province,'/prov/<string:prov_code>')
api.add_resource(Municipality,'/mun/<string:mun_code>')
api.add_resource(
    Job,
    '/job/<string:mun_code>',
    '/job/<string:mun_code>/',
    '/job/<string:mun_code>/<string:split>',
)


@app.route("/")
def hello_world():
   return f"{cat_config.app_name} {cat_config.app_version} API"

