import argparse
import glob
import logging
import os
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
        ERROR = auto()

    def __init__(self, mun_code, building=True, address=True):
        super(Work, self).__init__()
        self.mun_code = mun_code
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

    def run(self):
        mun_code = self.mun_code
        os.chdir(WORK_DIR)
        if not os.path.exists(mun_code):
            os.mkdir(mun_code)
        log = cat_config.setup_logger(log_path=mun_code)
        log.setLevel(logging.INFO)
        log.app_level = logging.INFO
        try:
            qgs = QgsSingleton()        
            CatAtom2Osm.create_and_run(mun_code, self.options)
            qgs.exitQgis()
        except Exception as e:
            msg = e.message if getattr(e, "message", "") else str(e)
            log.error(msg)
        for fp in glob.glob(os.path.join(mun_code, "*.zip")):
            os.remove(fp)

    def status(self):
        os.chdir(WORK_DIR)
        if os.path.exists(self.mun_code):
            fn = os.path.join(self.mun_code, "catatom2osm.log")
            with open(fn, "r") as fo:
                log = fo.read()
                if "ERROR" in log:
                    return Work.Status.ERROR
            fn = os.path.join(self.mun_code, "highway_names.csv")
            if os.path.exists(fn):
                return Work.Status.REVIEW
            fn = os.path.join(self.mun_code, "tasks")
            if os.path.exists(fn):
                return Work.Status.STATUS
            return Work.Status.RUNNING
        else:
            return Work.Status.AVAILABLE

    def log(self, from_line=0):
        os.chdir(WORK_DIR)
        log = []
        fn = os.path.join(self.mun_code, "catatom2osm.log")
        if os.path.exists(fn):
            with open(fn, "r") as fo:
                for i, line in enumerate(fo.readlines()):
                    if i >= from_line:
                        log.append(line.strip("\n"))
        return log, i
