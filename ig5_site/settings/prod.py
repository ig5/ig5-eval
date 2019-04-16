import os

from ig5_site.settings.base import *  # noqa

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = [os.environ["CURRENT_HOST"]]
