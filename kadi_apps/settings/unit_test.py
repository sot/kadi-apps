import os
from pathlib import Path

import kadi_apps

PORT = int(os.environ['KADI_APPS_PORT']) if 'KADI_APPS_PORT' in os.environ else 9123
DEBUG = True
TESTING = False

KADI_APPS_CONFIG_DIR = os.environ.get(
    "KADI_APPS_CONFIG_DIR",
    str(Path(kadi_apps.__file__).parent / "tests" / "data" / "config"),
)

LOG_LEVEL = 'INFO'
TOKEN_VERSION = (1, 0)
