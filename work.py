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

from catatom2osm import boundary
from catatom2osm import csvtools
from catatom2osm import config as cat_config
from catatom2osm import osmxml
from catatom2osm.app import CatAtom2Osm, QgsSingleton
from catatom2osm.boundary import get_districts
from catatom2osm.exceptions import CatValueError


WORK_DIR = os.path.join(os.environ['HOME'], 'results')
BACKUP_DIR = os.path.join(os.environ['HOME'], 'backup')
CACHE_DIR = os.path.join(os.environ['HOME'], 'cache')

dict2csv = csvtools.dict2csv
 
def csv2dict(csv_path):
    return csvtools.csv2dict(csv_path, single=False)

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
        linea=0,
        config={},
        socketio=None,
    ):
        super(Work, self).__init__()
        self.mun_code = mun_code
        self.user = user
        self.split = split
        self.linea = linea
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
        self.options.args = self.current_args
        self.options.args += (" " if self.options.args else "") +  mun_code
        self.report = self.search_report()
        self.get_options_from_report(self.report)
        if self.split:
            self.options.args += f" -s {self.split}"
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
        fp = self._path(*args)
        if not os.path.exists(fp):
            os.mkdir(self._path(*args))
        return fp

    def _path_remove(self, *args):
        if self._path_exists(*args):
            if os.path.isdir(self._path(*args)):
                shutil.rmtree(self._path(*args))
            else:
                os.remove(self._path(*args))
            return True
        return False

    def _get_file(self, *args, from_row=0):
        fn = self._path(*args)
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
        if self.status == Work.Status.AVAILABLE and os.path.exists(cache):
            shutil.copytree(cache, self.path, dirs_exist_ok=True)

    def _backup_files(self):
        backup = os.path.join(BACKUP_DIR, self.mun_code)
        if not os.path.exists(backup):
            os.mkdir(backup)
        for fp in glob.iglob(self._path("A.ES.SDGC.??.?????.zip")):
            fn = os.path.basename(fp)
            shutil.move(fp, os.path.join(backup, fn))
        backup = self._path_create("backup")
        if self._path_exists("highway_names.csv"):
            shutil.copy(self._path("highway_names.csv"), backup)
        if self._path_exists("review.txt"):
            shutil.copy(self._path("review.txt"), backup)
            review = csv2dict(self._path("review.txt"))
            for fixme in review.keys():
                fn = fixme + ".osm.gz"
                src = self._path(self.target_dir, self.tasks_dir, fn)
                dst = self._path("backup", fn)
                shutil.copy(src, dst)
        if self._path_exists(self.target_dir, self.tasks_dir):
            dst = self._path(self.target_dir, self.tasks_dir, "backup")
            shutil.copytree(backup, dst, dirs_exist_ok=True)
            
    def get_options_from_report(self, data):
        options = data.get("options", False)
        if options:
            if options.startswith("-b "):
                self.options.building = True
                self.options.address = False
            elif options.startswith("-d "):
                self.options.building = False
                self.options.address = True
            else:
                self.options.building = True
                self.options.address = True

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
            dst = self._path(self.target_dir, self.tasks_dir, taskname + '.osm.gz')
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
            target = self._path(self.target_dir, self.tasks_dir, filename)
            shutil.copyfile(tmpfn, target)
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
        fp = self._path("review.txt")
        target = self._path(self.target_dir, self.tasks_dir, "review.txt")
        review = csv2dict(fp)
        if sum([int(fixme[0]) for fixme in review.values()]) == 0:
            shutil.move(fp, target)

    def export(self):
        if self._path_exists(self.target_dir, self.tasks_dir):
            tasks = "/".join([self.mun_code, self.target_dir, self.tasks_dir])
            tmpfo, tmpfn = mkstemp()
            return shutil.make_archive(tmpfn, "zip", WORK_DIR, tasks)

    def watch_log(self, user_data):
        data = dict(user_data)
        while self.status != Work.Status.RUNNING:
            pass
        while self.status == Work.Status.RUNNING:
            data["job"] = self.get_dict()
            log = data["job"]["log"]
            if len(log) > 0:
                self.socketio.emit("updateJob", data, to=self.mun_code)
            self.socketio.sleep(0.5)
        data["job"] = self.get_dict()
        log = data["job"]["log"]
        if len(log) > 0:
            self.socketio.emit("updateJob", data, to=self.mun_code)
        if self.status == Work.Status.DONE:
            self.socketio.emit("done", data, to=self.mun_code)

    @property
    def current_args(self):
        if self.options.building and not self.options.address:
            return "-b"
        if self.options.address and not self.options.building:
            return "-d"
        return ""

    @property
    def tasks_dir(self):
        return "tasks" + self.current_args
    
    @property
    def target_dir(self):
        return self.split or ""

    @property
    def last_args(self):
        if self._path_exists(self.target_dir, "tasks-b"):
            return "" if self._path_exists(self.target_dir, "tasks-d") else "-b"
        if self._path_exists(self.target_dir, "tasks-d"):
            return "-d"
        return ""

    @property
    def next_args(self):
        return "" if not self.last_args else "-d" if self.last_args == "-b" else "-b"
    
    @property
    def type(self):
        type = "b" if self._path_exists(self.target_dir, "tasks-b") else ""
        type += "d" if self._path_exists(self.target_dir, "tasks-d") else ""
        return type

    def run(self):
        self._path_remove("report.txt")
        self._path_remove("catatom2osm.log")
        if not (self.options.address and self._path_exists("highway_names.csv")):
            self._path_remove("report.json")
        self._read_cache()
        socketio_logger = logging.getLogger("socketio.server")
        log = cat_config.setup_logger(log_path=self.path)
        log.handlers += socketio_logger.handlers
        log.setLevel(logging.INFO)
        log.app_level = logging.INFO
        cat_config.set_config(self.config)
        with open(self._path("user.json"), "w") as fo:
            json.dump(self.user, fo)
        try:
            qgs = QgsSingleton()
            os.chdir(self.path)
            CatAtom2Osm.create_and_run(self.path, self.options)
            qgs.exitQgis()
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            log.error(msg)
        self._backup_files()

    @property
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
                fp = self._path(self.target_dir, self.tasks_dir)
                if self._path_exists(self.target_dir, self.tasks_dir):
                    return Work.Status.DONE
                else:
                    return Work.Status.AVAILABLE
            return Work.Status.RUNNING
        else:
            return Work.Status.AVAILABLE

    def get_dict(self, msg=""):
        data = {
            "cod_municipio": self.mun_code,
            "propietario": Work.get_user(self.mun_code),
            "mensaje": msg,
            "linea": self.linea,
            "informe": self.report_txt,
            "report": self.report,
            "revisar": [],
            "callejero": [],
            "info": None,
            "next_args": self.next_args,
        }
        data["cod_division"] = self.split or ""
        status = self.status
        data["estado"] = status.name
        data["type"] = self.type
        data["log"] = self.log if status != Work.Status.AVAILABLE else []
        data["current_args"] = self.current_args
        data["edificios"] = self.options.building
        data["direcciones"] = self.options.address
        if status in [Work.Status.REVIEW, Work.Status.FIXME, Work.Status.DONE]:
            data["callejero"] = self.highway_names
        if status == Work.Status.FIXME or status == Work.Status.DONE:
            data["revisar"] = self.review
        if status != Work.Status.RUNNING:
            data["charla"] = self.chat
        if status == Work.Status.AVAILABLE:
            data["info"] = self.info
        return data

    @property
    def log(self):
        log, self.linea = self._get_file("catatom2osm.log", from_row=self.linea)
        return log

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
            data["src"] = hgwnames[cat][1]
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
                data["src"] = hgwnames[cat][1]
                data["osm_id"] = user["osm_id"]
                data["username"] = user["username"]
                hgwnames[cat] = [conv, data["src"], user["osm_id"], user["username"]]
                dict2csv(fn, hgwnames)
        return data

    @property
    def highway_names(self):
        highway_names = self._get_file(self.report_path or "", "highway_names.csv")[0]
        return [row.split("\t") for row in highway_names]

    def search_report(self):
        fn = "report.json"
        fp = self._path(fn)
        if self.current_args:
            fp = self._path(self.target_dir, self.tasks_dir, fn)
        elif self.target_dir:
            tasks = "tasks-" + self.type[:1] if self.type else "tasks"
            fp = self._path(self.target_dir, tasks, fn)
        report = self.get_report_json(fp)
        self.report_path = os.path.relpath(os.path.dirname(fp), self.path) if report else False
        if not self.split:
            self.split = report.get("split_id", None)
        return report

    def get_report_json(self, fp):
        if os.path.exists(fp):
            with open(fp, "r") as fo:
                report = json.load(fo)
            report.pop("min_level", None)
            report.pop("max_level", None)
            return report
        return {}

    @property
    def report_txt(self):
        return [] if self.report_path == False else self._get_file(self.report_path, "report.txt")[0] or []

    @property
    def review(self):
        review = []
        fp = self._path(self.report_path or "", "review.txt")
        if self._path_exists(fp):
            review = [
                self._get_fixme_dict(k, v)
                for k, v in csv2dict(self._path(fp)).items()
            ]
        return review

    def _clean_root(self):
        for fn in os.listdir(self.path):
            fp = self._path(fn)
            if not os.path.isdir(fp):
                keep = False
                exceptions = ["splits.json", "info", "user.json"]
                while len(exceptions) > 0 and not keep:
                    keep = fn.startswith(exceptions.pop())
                if not keep:
                    os.remove(fp)

    def _recover(self):
        report = []
        cwd = os.getcwd()
        if self._path_exists(self.target_dir):
            os.chdir(self._path(self.target_dir))
            report = glob.glob("**/report.txt", recursive=True)
        if not report:
            os.chdir(self.path)
            report = glob.glob("**/report.txt", recursive=True)
        os.chdir(cwd)
        if report:
            fp = os.path.dirname(report[0])
            source = self._path(self.target_dir if fp.startswith("tasks") else "", fp)
            for fn in os.listdir(source):
                if (
                    not fn.endswith(".osm.gz")
                    and fn != "backup"
                    and fn != "highway_names.csv"
                    and not fn.startswith("review.txt")
                ):
                    shutil.copy(self._path(source, fn), self.path)

    def delete(self):
        self._clean_root()
        self._path_remove("backup")
        self._path_remove(self.target_dir, self.tasks_dir)
        if self.target_dir and self._path_exists(self.target_dir):
            if len(os.listdir(self._path(self.target_dir))) == 0:
                self._path_remove(self.target_dir)
        self._recover()
        if not self._path_exists("report.txt"):
            self._path_remove("user.json")

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

    @property
    def splits(self):
        self._path_create()
        fp = os.path.join(CACHE_DIR, self.mun_code, "splits.json")
        if not self._path_exists("splits.json") and os.path.exists(fp):
            shutil.copy(fp, self.path)
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

    @property
    def chat(self):
        chat = []
        if self._path_exists("chat.json"):
            with open(self._path("chat.json"), "r") as fo:
                chat = json.load(fo)
        return chat

    @property
    def info(self):
        info = None
        fn = f"info_{self.split}.json" if self.split else "info.json"
        fp = os.path.join(CACHE_DIR, self.mun_code, fn)
        if os.path.exists(fp):
            with open(fp, "r") as fo:
                info = json.load(fo)
        return info

    def add_message(self, msg):
        chat = self.chat
        chat.append(msg)
        with open(self._path("chat.json"), "w") as fo:
            json.dump(chat, fo)
