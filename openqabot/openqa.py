import logging
from pprint import pformat

from openqa_client.client import OpenQA_Client

from .types import Data

logger = logging.getLogger("bot.openqa")


class openQAInterface:
    def __init__(self):
        self.openqa = OpenQA_Client(server="openqa.suse.de", scheme="https")

    def post_job(self, settings) -> None:
        logger.info("Openqa isos POST {}".format(pformat(settings)))
        try:
            self.openqa.openqa_request("POST", "isos", data=settings, retries=3)
        except Exception as e:
            logger.exception(e)
            logger.error("Post failed with {}".format(pformat(settings)))


    def get_jobs(self,data: Data):
        logger.debug("getting openqa for %s" % pformat(data))
        param = {}
        param["scope"] = "relevant"
        param["latest"] = "1"
        param["flavor"] = data.flavor
        param["distri"] = data.distri
        param["build"] = data.build
        param["version"] = data.version
        param["arch"] = data.arch
    
        ret = None
        try:
            ret = self.openqa.openqa_request("GET", "jobs", param)["jobs"]
        # TODO: correct handling
        except Exception as e:
            logger.exception(e)
            raise e
        return ret