import logging
import os

from flask import Flask, g, redirect, request, send_file
from flask_cors import CORS
from flask_restful import abort, Api, reqparse, Resource
from flask_socketio import SocketIO, join_room, leave_room

from config import get_config
from catatom2osm import config as cat_config
cat_config.get_user_config('catconfig.yaml')

from catatom2osm import csvtools
from catatom2osm.boundary import get_districts

import user
from work import Work, check_owner


WORK_DIR = os.environ['HOME']
app = Flask(__name__, instance_relative_config=True)
mode = app.config.get("ENV", "development")
app.config.from_object(get_config(mode))
origins = app.config["CLIENT_URL"]
cors = CORS(app, resources={r"/*": {"origins": origins}}, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins=origins)
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
        200, "Proceso finalizado"
    ),
    Work.Status.AVAILABLE: (
        200, "No procesado"
    ),
    Work.Status.ERROR: (
        502, "Terminó con error"
    ),
}


class Login(Resource):
    def get(self):
        callback = request.args.get('callback')
        return user.get_authorize_url(callback)

    @user.auth.login_required
    def put(self):
        return {"ping": "ok"}

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
        job = Work.validate(mun_code)
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
        self.post_parser.add_argument("building", type=bool, default=True)
        self.post_parser.add_argument("address", type=bool, default=True)
        self.post_parser.add_argument("idioma", type=str, default="es_ES")

    def get(self, mun_code, split=None):
        """Estado del proceso de un municipio."""
        linea = int(request.args.get("linea", 0))
        job = Work.validate(mun_code, split=split)
        status = job.status()
        msg = status_msg[status][1]
        log = []
        if status != Work.Status.AVAILABLE: 
            log, linea = job.log(linea)
        data = {
            "cod_municipio": mun_code,
            "cod_division": split or "",
            "estado": status.name,
            "propietario": Work.get_user(mun_code),
            "mensaje": msg,
            "linea": linea,
            "log": log,
            "informe": [],
            "report": {},
            "revisar": [],
        }
        if status != Work.Status.AVAILABLE and status != Work.Status.RUNNING: 
            data["informe"] = job.report()
            data["report"] = job.report_json()
            if "split_id" in data["report"]:
                data["cod_division"] = data["report"]["split_id"]
        if status == Work.Status.REVIEW:
            data["callejero"] = job.highway_names()
        if status == Work.Status.FIXME:
            data["revisar"] = job.review()
        return data

    @user.auth.login_required
    @check_owner
    def post(self, mun_code, split=None):
        """Procesa un municipio."""
        args = self.post_parser.parse_args()
        job = Work.validate(mun_code, split, **args, socketio=socketio)
        status = job.status()
        if status not in [Work.Status.AVAILABLE, Work.Status.ERROR, Work.Status.REVIEW]:
            msg = status_msg[status][1].format(mun_code)
            abort(status_msg[status][0], message=msg)
        try:
            job.start()
            data = {"username": g.user_data["username"], "room": mun_code}
            socketio.emit("create_job", data, to=mun_code)
            socketio.start_background_task(job.watchLog)
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            abort(500, message=msg)
        return {
            "estado": Work.Status.RUNNING.name,
            "cod_municipio": mun_code,
            "cod_division": split or "",
            "mensaje": "Procesando...",
        }

    @user.auth.login_required
    def put(self, mun_code, split=None):
        job = Work.validate(mun_code, split=split)
        file = request.files["file"]
        try:
            status = job.save_file(file)
        except Exception as e:
            abort(500, message=str(e))
        if status == "notfound":
            abort(400, message="Sólo archivos de tareas existentes")
        if status == "notvalid":
            abort(400, message="No es un archivo gzip válido")

    @user.auth.login_required
    @check_owner
    def delete(self, mun_code, split=None):
        """Eliminar proceso."""
        __ = request.data  # https://github.com/pallets/flask/issues/4546
        job = Work.validate(mun_code, split)
        if not job.delete():
            abort(410, message="No se pudo eliminar")
        data = {"username": g.user_data["username"], "room": mun_code}
        socketio.emit("delete_job", data, to=mun_code)
        return {
            "cod_municipio": mun_code,
            "cod_division": split or "",
            "propietario": None,
            "estado": Work.Status.AVAILABLE.name,
            "mensaje": "Proceso eliminado correctamente",
            "linea": 0,
            "log": "",
            "informe": [],
            "report": [],
            "revisar": [],
        }


class Highway(Resource):

    @user.auth.login_required
    def put(self, mun_code):
        """Edita una entrada del callejero"""
        job = Work.validate(mun_code, socketio=socketio)
        cat = request.form["cat"]
        conv = request.form["conv"]
        data = {}
        try:
            data = job.update_highway_name(cat, conv)
        except OSError as e:
            abort(501, message=str(e))
        return data

class Export(Resource):

    def get(self, mun_code):
        """Exporta carpeta de tareas"""
        job = Work.validate(mun_code)
        data = job.export()
        if data:
            return send_file(data, download_name=mun_code + ".zip")
        else:
            abort(404, message="Proceso no encontrado")


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
api.add_resource(Export,'/export/<string:mun_code>')
api.add_resource(Highway,'/hgw/<string:mun_code>')

@app.route("/")
def hello_world():
    return f"{cat_config.app_name} {cat_config.app_version} API"


@socketio.on("chat")
def handle_send(data):
    socketio.emit("chat", data, to=data["room"])

@socketio.on("updateJob")
def handle_update(msg, room):
    socketio.emit("updateJob", msg, to=room, include_self=False)

@socketio.on("join")
def on_join(data):
    room = data["room"]
    join_room(room)
    users = socketio.server.manager.rooms["/"].get(room, [])
    data["participants"] = len(users)
    socketio.emit("join", data, to=room)
    return data

@socketio.on('leave')
def on_leave(data):
    room = data["room"]
    users = socketio.server.manager.rooms["/"].get(room, [])
    leave_room(room)
    data["participants"] = len(users)
    if len(users) > 0:
        socketio.emit("leave", data, to=room)
    return data


if __name__ == '__main__':
    flask_port = os.environ["FLASK_PORT"]
    socketio.run(app, "0.0.0.0", flask_port, log_output=True)
