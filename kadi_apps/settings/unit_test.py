from pathlib import Path

PORT = 9000
DEBUG = True
TESTING = False

# DATA_DIR = f'/proj/web-kadi-test/api-data'
KADI_APPS_CONFIG_DIR = str(Path(__file__).parent.parent / 'tests' / 'data' / 'config')
LOG_LEVEL = 'INFO'
TOKEN_VERSION = (1, 0)
