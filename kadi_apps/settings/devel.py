import os
import datetime
from pathlib import Path

import kadi_apps

PORT = int(os.environ['KADI_APPS_PORT']) if 'KADI_APPS_PORT' in os.environ else None
DEBUG = True
TESTING = False

KADI_APPS_CONFIG_DIR = os.environ.get(
    "KADI_APPS_CONFIG_DIR",
    str(Path(kadi_apps.__file__).parent / "tests" / "data" / "config"),
)
LOG_LEVEL = 'INFO'
TOKEN_VERSION = (1, 0)

SEND_FILE_MAX_AGE_DEFAULT = 5

TOKEN_VALIDITY = datetime.timedelta(seconds=10)
REFRESH_TOKEN_VALIDITY = datetime.timedelta(minutes=2)
REFRESH_TOKEN_MARGIN = datetime.timedelta(seconds=20)