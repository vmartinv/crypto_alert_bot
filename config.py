import secrets
from pathlib import Path

TG_TOKEN = secrets.TG_TOKEN
CC_API_KEY = secrets.CC_API_KEY
DB_FILENAME = str(Path("data") / "db.sqlite")
PRICES_DB_FILENAME = str(Path("data") / "prices.sqlite")
INDICATORS_CACHE_DB_FILENAME  = str(Path("data") / "indicators_cache.sqlite")
HELP_FILENAME = 'readme.md'
