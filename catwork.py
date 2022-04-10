import argparse
import glob
import logging
import os
from multiprocessing import Process

from catatom2osm import config as cat_config
from catatom2osm.app import CatAtom2Osm, QgsSingleton


WORK_DIR = os.environ['HOME']


class CatWork(Process):
    def __init__(self, mun_code):
        super(CatWork, self).__init__()
        self.mun_code = mun_code
        self.options = argparse.Namespace(
            path = [mun_code],
            args = mun_code,
            address=True,
            building=True,
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

    def run(self):
        mun_code = self.mun_code
        qgs = QgsSingleton()        
        os.chdir(WORK_DIR)
        if not os.path.exists(mun_code):
            os.mkdir(mun_code)
        log = cat_config.setup_logger(log_path=mun_code)
        log.setLevel(logging.INFO)
        log.app_level = logging.INFO
        CatAtom2Osm.create_and_run(mun_code, self.options)
        for fp in glob.glob(os.path.join(mun_code, "*.zip")):
            os.remove(fp)
        qgs.exitQgis()

