from pathlib import Path

import kadi_apps

DEBUG = True
TESTING = False

KADI_APPS_CONFIG_DIR = str(Path(kadi_apps.__file__).parent / 'tests' / 'data' / 'config')
LOG_LEVEL = 'INFO'
TOKEN_VERSION = (1, 0)
