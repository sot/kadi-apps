from pathlib import Path

PASSWORDS = Path(__file__).parent.parent / 'users.json'
JWT_SECRET = 'stupid_secret'

ASTROMON_OBS_DATA = Path(__file__).parent.parent / 'astromon'
