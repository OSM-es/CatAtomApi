import argparse
import glob
import gzip
import json
import logging
import os
import shutil
import subprocess
import re
from telnetlib import STATUS
import time
from enum import Enum, auto
from functools import wraps
from multiprocessing import Process

from tempfile import mkstemp
from flask import g
from flask_restful import abort
from werkzeug.utils import secure_filename

from csvtools import csv2dict, dict2csv
from catatom2osm import boundary
from catatom2osm import config as cat_config
from catatom2osm import osmxml
from catatom2osm.app import CatAtom2Osm, QgsSingleton
from catatom2osm.boundary import get_districts
from catatom2osm.exceptions import CatValueError


WORK_DIR = os.path.join(os.environ['HOME'], 'results')
BACKUP_DIR = os.path.join(os.environ['HOME'], 'backup')
CACHE_DIR = os.path.join(os.environ['HOME'], 'cache')

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
        config={},
        socketio=None,
    ):
        super(Work, self).__init__()
        self.mun_code = mun_code
        self.user = user
        self.split = split
        self.config = config
        self.socketio = socketio
        self.path = os.path.join(WORK_DIR, self.mun_code)
        self.options = argparse.Namespace(
            path = [mun_code],
            args = "",
            address=address,
            building=building,
            comment=False,
            config_file=False,
            download=False,
            info=False,
            generate_config=False,
            manual=False,
            zoning=False,
            list="",
            split=self.split,
            parcel=[],
            log_level='INFO',
        )
        self.options.args = self.current_args() + mun_code
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

    @staticmethod
    def _get_fixme_dict(k, v):
        return {
            "filename": k + ".osm.gz",
            "fixmes": v[0] if len(v) > 0 else None,
            "osm_id": v[1] if len(v) > 1 else None,
            "username": v[2] if len(v) > 2 else None,
            "locked": v[3] if len(v) > 3 else None,
        }

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

    def _path_islink(self, *args):
        return os.path.islink(self._path(*args))

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

    def _read_cache(self):
        self._path_create()
        cache = os.path.join(CACHE_DIR, self.mun_code)
        if self.status() == Work.Status.AVAILABLE and os.path.exists(cache):
            shutil.copytree(cache, self.path, dirs_exist_ok=True)

    def _backup_files(self):
        backup = os.path.join(BACKUP_DIR, self.mun_code)
        if not os.path.exists(backup):
            os.mkdir(backup)
        for fp in glob.iglob(self._path("A.ES.SDGC.??.?????.zip")):
            fn = os.path.basename(fp)
            shutil.move(fp, os.path.join(backup, fn))
        self._path_create("backup")
        if self._path_exists("highway_names.csv"):
            shutil.copy(self._path("highway_names.csv"), self._path("backup"))
        if self._path_exists("review.txt"):
            shutil.copy(self._path("review.txt"), self._path("backup"))
            review = csv2dict(self._path("review.txt"))
            for fixme in review.keys():
                src = self._path('tasks', fixme + '.osm.gz')
                dst = self._path('backup', fixme + '.osm.gz')
                shutil.copy(src, dst)

    def lock_fixme(self, filename):
        fn = self._path("review.txt")
        review = csv2dict(fn)
        taskname = filename.split(".")[0]
        fixme = []
        if taskname in review:
            fixmes = review[taskname][0]
            fixme = [
                str(fixmes),
                g.user_data["osm_id"],
                g.user_data["username"],
                "true",
            ]
            review[taskname] = fixme
            dict2csv(fn, review)
        return self._get_fixme_dict(taskname, fixme)

    def unlock_fixme(self, filename):
        fn = self._path("review.txt")
        review = csv2dict(fn)
        review_bck = csv2dict(self._path("backup", "review.txt"))
        taskname = filename.split(".")[0]
        fixme = []
        if taskname in review:
            src = self._path('backup', taskname + '.osm.gz')
            dst = self._path('tasks', taskname + '.osm.gz')
            shutil.copy(src, dst)
            fixmes = review_bck[taskname][0]
            fixme = [str(fixmes)]
            review[taskname] = fixme
            dict2csv(fn, review)
        return self._get_fixme_dict(taskname, fixme)

    def save_fixme(self, file):
        tmpfo, tmpfn = mkstemp()
        file.save(tmpfn)
        try:
            with gzip.open(tmpfn) as fo:
                data = osmxml.deserialize(fo)
                comment = data.tags.get("comment", "")
                match = re.search(" ([0-9A-Z]{14})$", comment)
                if match:
                    filename = match.group(1) + ".osm.gz"
                else:
                    filename = secure_filename(file.filename)
        except (gzip.BadGzipFile, osmxml.etree.Error) as e:
            return "notvalid"
        fn = self._path("review.txt")
        review = csv2dict(fn)
        taskname = filename.split(".")[0]
        if filename.endswith(".gz") and taskname in review:
            shutil.copyfile(tmpfn, self._path("tasks", filename))
            os.remove(tmpfn)
            fixmes = 0
            for el in data.elements:
                if "fixme" in el.tags:
                    fixmes += 1
            fixme = [str(fixmes), g.user_data["osm_id"], g.user_data["username"]]
            review[taskname] = fixme
            dict2csv(fn, review)
            return self._get_fixme_dict(taskname, fixme)
        os.remove(tmpfn)
        return "notfound"

    def clear_fixmes(self):
        fn = self._path("review.txt")
        review = csv2dict(fn)
        if sum([int(fixme[0]) for fixme in review.values()]) == 0:
            os.rename(self._path("review.txt"), self._path("review.txt.bak"))

    def export(self):
        if self._path_exists("tasks"):
            tmpfo, tmpfn = mkstemp();
            tasks = self._path("tasks")
            return shutil.make_archive(tmpfn, "zip", tasks)

    def watch_log(self, user_data):
        while self.status() != Work.Status.RUNNING:
            pass
        lines = 0
        while self.status() == Work.Status.RUNNING:
            log, lines = self.log(lines)
            if len(log) > 0:
                self.socketio.emit("updateJob", user_data, to=self.mun_code)
            self.socketio.sleep(0.5)
        log, lines = self.log(lines)
        if len(log) > 0:
            self.socketio.emit("updateJob", user_data, to=self.mun_code)
        if self.status() == Work.Status.DONE:
            self.socketio.emit("done", to=self.mun_code)

    def current_args(self):
        if self.options.building and not self.options.address:
            return "-b"
        if self.options.address and not self.options.building:
            return "-d"
        return ""

    def next_args(self):
        if self.status() == self.Status.DONE:
            if self._path_islink("tasks-b") and not self._path_exists("tasks-d"):
                return "-d"
            if self._path_islink("tasks-d") and not self._path_exists("tasks-b"):
              return "-b"
        return ""

    def last_args(self):
        if self.status() == self.Status.DONE:
            if self._path_islink("tasks-b") and not self._path_exists("tasks-d"):
                return "-b"
            if self._path_islink("tasks-d") and not self._path_exists("tasks-b"):
              return "-d"
        return ""

    def run(self):
        self._read_cache()
        if self.last_args():
            src = self._path("tasks")
            dst = self._path("tasks" + self.last_args())
            os.remove(dst)
            os.rename(src, dst)
        self._path_remove("catatom2osm.log")
        self._path_remove("report.txt")
        socketio_logger = logging.getLogger("socketio.server")
        log = cat_config.setup_logger(log_path=self._path())
        log.handlers += socketio_logger.handlers
        log.setLevel(logging.INFO)
        log.app_level = logging.INFO
        cat_config.set_config(self.config)
        with open(self._path("user.json"), "w") as fo:
            json.dump(self.user, fo)
        try:
            qgs = QgsSingleton()
            os.chdir(self._path())
            CatAtom2Osm.create_and_run(self._path(), self.options)
            qgs.exitQgis()
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            log.error(msg)
        target = self.current_args()
        if target and not self._path_islink("tasks" + target):
            os.symlink(self._path("tasks"), self._path("tasks" + target))
        self._backup_files()

    def status(self):
        if self._path_exists() and self._path_exists("user.json"):
            try:
                with open(self._path("catatom2osm.log"), "r") as fo:
                    log = fo.read()
                    if "ERROR" in log:
                        return Work.Status.ERROR
            except FileNotFoundError:
                pass
            if self._path_exists("report.txt"):
                if self._path_exists("highway_names.csv"):
                    return Work.Status.REVIEW
                if self._path_exists("review.txt"):
                    return Work.Status.FIXME
                if self._path_exists("tasks"):
                    if not self.split is None:
                        if not self._path_exists("tasks", self.split):
                            return Work.Status.AVAILABLE
                    return Work.Status.DONE
            return Work.Status.RUNNING
        else:
            return Work.Status.AVAILABLE

    def log(self, from_row=0):
        return self._get_file("catatom2osm.log", from_row)

    def get_highway_name(self, street):
        if self._path_exists("address.geojson"):
            with open(self._path("address.geojson"), "r") as fo:
                data = json.load(fo)
            if street:
                filtered = [
                    feat for feat in data['features']
                    if feat['properties']['TN_text'] == street
                ]
                data['features'] = filtered
            return data
        return {}

    def undo_highway_name(self, data):
        if self._path_exists("highway_names.csv"):
            fn = self._path("highway_names.csv")
            hgwnames = csv2dict(fn)
            hgwnames_bck = csv2dict(self._path("backup", "highway_names.csv"))
            cat = data["cat"]
            conv = data["conv"]
            hgwnames[cat] = hgwnames_bck[cat]
            data["conv"] = hgwnames[cat][0]
            dict2csv(fn, hgwnames)
        return data
        

    def update_highway_name(self, data):
        if self._path_exists("highway_names.csv"):
            fn = self._path("highway_names.csv")
            hgwnames = csv2dict(fn)
            cat = data["cat"]
            conv = data["conv"]
            if cat in hgwnames:
                user = getattr(g, "user_data", "")
                data["osm_id"] = user["osm_id"]
                data["username"] = user["username"]
                hgwnames[cat] = [conv, user["osm_id"], user["username"]]
                dict2csv(fn, hgwnames)
        return data

    def highway_names(self):
        highway_names = self._get_file("highway_names.csv")[0]
        if not highway_names:
            highway_names = self._get_file("tasks/highway_names.csv")[0]
        return [row.split("\t") for row in highway_names]

    def report(self):
        return self._get_file("report.txt")[0]

    def report_json(self):
        if self._path_exists("report.json"):
            with open(self._path("report.json"), "r") as fo:
                report = json.load(fo)
            report.pop("min_level", None)
            report.pop("max_level", None)
            return report
        return {}

    def review(self):
        review = []
        fn = "review.txt"
        if not self._path_exists(fn):
            fn = "review.txt.bak"
        if self._path_exists(fn):
            review = [
                self._get_fixme_dict(k, v)
                for k, v in csv2dict(self._path(fn)).items()
            ]
        return review

    def delete(self):
        if self.split:
            return self._path_remove("tasks", self.split)
        return self._path_remove()

    def _splits(self):
        divisiones = [
            {
                "osm_id": district[1],
                "nombre": f"{'  ' if district[0] else ''}{district[2]} {district[3]}",
            } 
            for district in get_districts(self.mun_code)
        ]
        with open(self._path("splits.json"), "w") as fo:
            json.dump(divisiones, fo)
        return divisiones

    def splits(self):
        self._path_create()
        if self._path_exists("splits.json"):
            with open(self._path("splits.json"), "r") as fo:
                divisiones = json.load(fo)
            p = Process(target=self._splits)
            p.start()
        else:
            divisiones = self._splits()
        return {
            "cod_municipio": self.mun_code,
            "divisiones": divisiones,
        }

    def chat(self):
        chat = []
        if self._path_exists("chat.json"):
            with open(self._path("chat.json"), "r") as fo:
                chat = json.load(fo)
        return chat

    def info(self):
        info = None
        fn = f"info_{self.split}.json" if self.split else "info.json"
        fp = os.path.join(CACHE_DIR, self.mun_code, fn)
        if os.path.exists(fp):
            with open(fp, "r") as fo:
                info = json.load(fo)
        return info

    def add_message(self, msg):
        chat = self.chat()
        chat.append(msg)
        with open(self._path("chat.json"), "w") as fo:
            json.dump(chat, fo)