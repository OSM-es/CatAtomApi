import argparse
import glob
import json
import logging
import os
import shutil
import subprocess
from enum import Enum, auto
from multiprocessing import Process

from catatom2osm import boundary
from catatom2osm import config as cat_config
from catatom2osm.app import CatAtom2Osm, QgsSingleton


WORK_DIR = os.environ['HOME']


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

    def run(self):
        mun_code = self.mun_code
        self._path_create()
        self._path_remove("catatom2osm.log")
        self._path_remove("report.txt")
        log = cat_config.setup_logger(log_path=self._path())
        log.setLevel(logging.INFO)
        log.app_level = logging.INFO
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
        review = self.review()
        if self._path_exists():
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
                return json.loads(fo.read())
        return {}

    def review(self):
        review = subprocess.run(
            ["bin/review.sh", self.mun_code], capture_output=True, text=True
        )
        output = review.stdout.strip("\n")
        if output:
            return output.split("\n")
        return []

