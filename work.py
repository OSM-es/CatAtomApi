import argparse
import glob
import gzip
import json
import logging
import os
import shutil
import subprocess
from enum import Enum, auto
from functools import wraps
from multiprocessing import Process

from tempfile import mkstemp
from flask import g
from flask_restful import abort
from werkzeug.utils import secure_filename

from catatom2osm import boundary
from catatom2osm import config as cat_config
from catatom2osm.app import CatAtom2Osm, QgsSingleton
from catatom2osm.exceptions import CatValueError


WORK_DIR = os.environ['HOME']


def check_owner(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        mun_code = kwargs.get("mun_code", "")
        user = Work.get_user(mun_code)
        if user and user["osm_id"] != g.user_data["osm_id"]:
            msg = f"Proceso bloqueado por {user['username']} ({user['osm_id']})"
            abort(409, message=msg)
        return f(*args, **kwargs)
    return decorated_function


class Work(Process):

    class Status(Enum):
        AVAILABLE = auto()
        RUNNING = auto()
        DONE = auto()
        REVIEW = auto()
        FIXME = auto()
        ERROR = auto()

    def __init__(
        self,
        mun_code,
        user=None,
        split=None,
        building=True,
        address=True,
        idioma="es_ES",
    ):
        super(Work, self).__init__()
        self.mun_code = mun_code
        self.user = user
        self.split = split
        self.idioma = idioma
        self.path = os.path.join(WORK_DIR, self.mun_code)
        self.options = argparse.Namespace(
            path = [mun_code],
            args = "",
            address=address,
            building=building,
            comment=False,
            config_file=False,
            download=False,
            generate_config=False,
            manual=False,
            zoning=False,
            list="",
            split=self.split,
            parcel=[],
            log_level='INFO',
        )
        if address and not building:
            self.options.args += "-d "
        if building and not address:
            self.options.args += "-b "
        self.options.args += mun_code
        if self.split:
            self.options.args += f"-s {self.split}"
        self.osm_id, self.name = boundary.get_municipality(mun_code)

    @staticmethod
    def get_user(mun_code):
        fn = os.path.join(WORK_DIR, mun_code)
        if os.path.exists(fn):
            fn = os.path.join(fn, "user.json")
            if os.path.exists(fn):
                with open(fn, "r") as fo:
                    return json.load(fo)

    @staticmethod
    def validate(mun_code, split=None, **kwargs):
        user = getattr(g, "user_data", "")
        try:
            job = Work(mun_code, user, split, **kwargs)
        except CatValueError as e:
            abort(404, message=str(e))
        return job

    def _path(self, *args):
        return os.path.join(self.path, *args)

    def _path_exists(self, *args):
        return os.path.exists(self._path(*args))

    def _path_create(self, *args):
        if not self._path_exists(*args):
            os.mkdir(self._path(*args))

    def _path_remove(self, *args):
        if self._path_exists(*args):
            if os.path.isdir(self._path(*args)):
                shutil.rmtree(self._path(*args))
            else:
                os.remove(self._path(*args))
            return True
        return False

    def _get_file(self, filename, from_row=0):
        fn = self._path(filename)
        rows = []
        i = 0
        if os.path.exists(fn):
            with open(fn, "r") as fo:
                for row in fo.readlines():
                    if i >= from_row:
                        rows.append(row.strip("\n"))
                    i += 1
        return rows, i

    def save_file(self, file):
        filename = secure_filename(file.filename)
        if filename.endswith(".gz"):
            filename = self._path("tasks", filename)
        else:
            return "notfound"
        if os.path.exists(filename):
            tmpfo, tmpfn = mkstemp();
            file.save(tmpfn)
            try:
                with gzip.open(tmpfn) as fo:
                    fo.read()
            except gzip.BadGzipFile:
                return "notvalid"
            shutil.copyfile(tmpfn, filename)
            os.remove(tmpfn)
            return "ok"
        return "notfound"

    def run(self):
        mun_code = self.mun_code
        self._path_create()
        self._path_remove("catatom2osm.log")
        self._path_remove("report.txt")
        gunicorn_logger = logging.getLogger('gunicorn.error')
        log = cat_config.setup_logger(log_path=self._path())
        log.handlers += gunicorn_logger.handlers
        log.setLevel(gunicorn_logger.level)
        log.app_level = gunicorn_logger.level
        cat_config.set_config(dict(language=self.idioma))
        with open(self._path("user.json"), "w") as fo:
            fo.write(json.dumps(self.user))
        try:
            qgs = QgsSingleton()
            os.chdir(self._path())
            CatAtom2Osm.create_and_run(self._path(), self.options)
            qgs.exitQgis()
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            log.error(msg)
        for fp in glob.glob(self._path("*.zip")):
            os.remove(fp)

    def status(self):
        review = self.review(status=True)
        if self._path_exists() and self._path_exists("user.json"):
            if self._path_exists("catatom2osm.log"):
                with open(self._path("catatom2osm.log"), "r") as fo:
                    log = fo.read()
                    if "ERROR" in log:
                        return Work.Status.ERROR
            if self._path_exists("report.txt"):
                if self._path_exists("highway_names.csv"):
                    return Work.Status.REVIEW
                if len(review) > 0:
                    return Work.Status.FIXME
                if self._path_exists("tasks"):
                    if not self.split is None:
                        if not self._path.exists("tasks", self.split):
                            return Work.Status.AVAILABLE
                    return Work.Status.DONE
            return Work.Status.RUNNING
        else:
            return Work.Status.AVAILABLE

    def log(self, from_row=0):
        return self._get_file("catatom2osm.log", from_row)

    def report(self):
        return self._get_file("report.txt")[0]

    def report_json(self):
        if self._path_exists("report.json"):
            with open(self._path("report.json"), "r") as fo:
                report = json.loads(fo.read())
            report.pop("min_level", None)
            report.pop("max_level", None)
            return report
        return {}

    def review(self, status=False):
        review = []
        if self._path_exists("tasks"):
            for fn in os.listdir(self._path("tasks")):
                if fn.endswith(".osm.gz"):
                    with gzip.open(self._path("tasks", fn)) as fo:
                        if b"fixme" in fo.read():
                            review.append(fn)
                            if status:
                                break
        return sorted(review)

    def delete(self):
        if self.split:
            return self._path_remove("tasks", self.split)
        return self._path_remove()
