import datetime

# PORT is not set in test
DEBUG = True
TESTING = False

KADI_APPS_CONFIG_DIR = '/export/servers/kadi-test/kadi-apps-config'
LOG_LEVEL = 'INFO'
TOKEN_VERSION = (1, 0)

TOKEN_VALIDITY = datetime.timedelta(minutes=10)
REFRESH_TOKEN_VALIDITY=datetime.timedelta(days=365)
REFRESH_TOKEN_MARGIN = datetime.timedelta(days=10)
