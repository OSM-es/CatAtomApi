import argparse
import glob
import logging
import os
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

    def __init__(self, mun_code, building=True, address=True):
        super(Work, self).__init__()
        self.mun_code = mun_code
        self.path = os.path.join(WORK_DIR, self.mun_code)
        self.options = argparse.Namespace(
            path = [mun_code],
            args = mun_code,
            address=address,
            building=building,
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
        self.osm_id, self.name = boundary.get_municipality(mun_code)

    def _path(self, *args):
        return os.path.join(self.path, *args)

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
        if not os.path.exists(self._path()):
            os.mkdir(self._path())
        log = cat_config.setup_logger(log_path=self._path())
        log.setLevel(logging.INFO)
        log.app_level = logging.INFO
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
        if os.path.exists(self._path()):
            if os.path.exists(self._path("catatom2osm.log")):
                with open(self._path("catatom2osm.log"), "r") as fo:
                    log = fo.read()
                    if "ERROR" in log:
                        return Work.Status.ERROR
            if os.path.exists(self._path("highway_names.csv")):
                return Work.Status.REVIEW
            if os.path.exists(self._path("review.txt")):
                return Work.Status.FIXME
            if os.path.exists(self._path("tasks")):
                return Work.Status.DONE
            return Work.Status.RUNNING
        else:
            return Work.Status.AVAILABLE

    def log(self, from_row=0):
        return self._get_file("catatom2osm.log", from_row)
    
    def report(self):
        return self._get_file("report.txt")[0]

    def review(self):
        review = subprocess.run(
            ["bin/review.sh", self.mun_code], capture_output=True, text=True
        )
        output = review.stdout.strip("\n")
        return output.split("\n")

