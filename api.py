import json
import logging
import os

from flask import Flask, g, request, send_file
from flask_cors import CORS
from flask_restful import abort, Api, reqparse, Resource
from flask_socketio import SocketIO, join_room, leave_room

from config import Config
from catatom2osm import config as cat_config
cat_config.get_user_config('catconfig.yaml')

from catatom2osm import csvtools

import auth
import schema
from work import Work, check_owner


app = Flask(__name__, instance_relative_config=True)
app.config.from_object(Config)
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

APP_DIR = os.environ['HOME']
for fn in ['results', 'backup', 'cache']:
    p = os.path.join(APP_DIR, fn)
    if not os.path.exists(p):
        os.mkdir(p)


@app.route('/login')
def login():
    return auth.login()

@app.route('/authorize')
def authorize():
    return auth.authorize()

@app.route('/logout')
def logout():
    return auth.logout()

@app.route('/user')
def user_info():
    return auth.user()


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
            {
                "cod_municipio": mun[0],
                "nombre": mun[2],
                "estado": Work(mun[0]).status.name,
            }
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
        return job.splits


class Job(Resource):
    def __init__(self):
        self.parser = schema.JobSchema()

    def get(self, mun_code=None, split=None):
        """Estado del proceso de un municipio."""
        if not mun_code:
            return Work.list_jobs()
        args = self.parser.load(request.args)
        job = Work.validate(mun_code, split, **args)
        data = job.get_dict()
        data["mensaje"] = status_msg[job.status][1]
        return data

    @auth.auth.login_required
    @check_owner
    def post(self, mun_code, split=None):
        """Procesa un municipio."""
        data = json.loads(request.data)
        args = self.parser.load(data)
        job = Work.validate(mun_code, split, **args, socketio=socketio)
        status = job.status
        if (
            (status == Work.Status.DONE and job.current_args == job.last_args)
            or status in [Work.Status.FIXME, Work.Status.RUNNING]
        ):
            msg = status_msg[status][1].format(mun_code)
            abort(status_msg[status][0], message=msg)
        try:
            job.start()
            data = dict(**g.user_data, room=mun_code)
            socketio.emit("createJob", data, to=mun_code)
            socketio.start_background_task(job.watch_log, g.user_data)
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            abort(500, message=msg)
        return job.get_dict("Procesando...")

    @auth.auth.login_required
    @check_owner
    def delete(self, mun_code, split=None):
        """Eliminar proceso."""
        __ = request.data  # https://github.com/pallets/flask/issues/4546
        args = self.parser.load(request.args)
        job = Work.validate(mun_code, split, **args)
        job.delete()
        job = Work(mun_code)
        data = dict(**g.user_data, room=mun_code)
        data["job"] = job.get_dict("Proceso eliminado correctamente")
        socketio.emit("deleteJob", data, to=mun_code)
        return data["job"]


class Highway(Resource):

    def get(self, mun_code):
        """Devuelve direcciones de la calle"""
        street = request.args.get('street', '')
        job = Work.validate(mun_code, socketio=socketio)
        return job.get_highway_name(street)

    @auth.auth.login_required
    def post(self, mun_code):
        """Restaura una entrada del callejero"""
        job = Work.validate(mun_code, socketio=socketio)
        return job.undo_highway_name(request.json)

    @auth.auth.login_required
    def put(self, mun_code):
        """Edita una entrada del callejero"""
        job = Work.validate(mun_code, socketio=socketio)
        data = {}
        try:
            data = job.update_highway_name(request.json)
            socketio.emit("highway", data, to=mun_code)
        except OSError as e:
            abort(501, message=str(e))
        return data


class Fixme(Resource):

    @auth.auth.login_required
    def get(self, mun_code, split=None):
        job = Work.validate(mun_code, split)
        fixme = request.args.get('fixme', None)
        status = job.lock_fixme(fixme)
        socketio.emit("fixme", status, to=mun_code)
        return status

    @auth.auth.login_required
    def post(self, mun_code, split=None):
        job = Work.validate(mun_code, split)
        fixme = request.json.get('fixme', None)
        status = job.unlock_fixme(fixme)
        socketio.emit("fixme", status, to=mun_code)
        return status

    @auth.auth.login_required
    def put(self, mun_code, split=None):
        job = Work.validate(mun_code, split)
        file = request.files["file"]
        try:
            status = job.save_fixme(file)
        except Exception as e:
            abort(500, message=str(e))
        if status == "notfound":
            abort(400, message="Sólo archivos de tareas existentes")
        if status == "notvalid":
            abort(400, message="No es un archivo gzip válido")
        socketio.emit("fixme", status, to=mun_code)
        return status

    @auth.auth.login_required
    @check_owner
    def delete(self, mun_code, split=None):
        job = Work.validate(mun_code, split)
        job.get_dict(status_msg[Work.Status.DONE])
        job.clear_fixmes()
        socketio.emit("done", dict(**g.user_data, room=mun_code), to=mun_code)
        return job.get_dict(status_msg[Work.Status.DONE])


class Export(Resource):
    def __init__(self):
        self.parser = schema.JobSchema()

    def get(self, mun_code, split=None):
        """Exporta carpeta de tareas"""
        args = self.parser.load(request.args)
        job = Work.validate(mun_code, split, **args)
        data = job.export()
        if data:
            return send_file(data, download_name=mun_code + ".zip")
        else:
            abort(404, message="Proceso no encontrado")


api.add_resource(Provinces, '/prov')
api.add_resource(Province, '/prov/<string:prov_code>')
api.add_resource(Municipality, '/mun/<string:mun_code>')
api.add_resource(
    Job,
    '/job',
    '/job/',
    '/job/<string:mun_code>',
    '/job/<string:mun_code>/',
    '/job/<string:mun_code>/<string:split>',
)
api.add_resource(Highway, '/hgw/<string:mun_code>')
api.add_resource(
    Fixme,
    '/fixme/<string:mun_code>',
    '/fixme/<string:mun_code>/',
    '/fixme/<string:mun_code>/<string:split>',
)
api.add_resource(
    Export,
    '/export/<string:mun_code>',
    '/export/<string:mun_code>/',
    '/export/<string:mun_code>/<string:split>',
)

@app.route("/")
def hello_world():
    return f"{cat_config.app_name} {cat_config.app_version} API"

@socketio.on("disconnect")
def handle_disconnect():
    data = {"username": request.args["username"]}
    for room in list(socketio.server.manager.rooms["/"].keys()):
        users = socketio.server.manager.rooms["/"].get(room)
        if room and len(room) == 5 and request.sid in users:
            data["room"] = room
            leave_room(room)
            data["participants"] = len(users)
            if len(users) > 0:
                socketio.emit("leave", data, to=room)

@socketio.on("chat")
def handle_send(data):
    room = data["room"]
    job = Work.validate(room)
    job.add_message(data)
    socketio.emit("chat", data, to=room)

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
