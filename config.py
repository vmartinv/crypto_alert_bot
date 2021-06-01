import secrets
from pathlib import Path

TG_TOKEN = secrets.TG_TOKEN
CC_API_KEY = secrets.CC_API_KEY
DB_FILENAME = str(Path("data") / "db.2.sqlite")
PRICES_DB_FILENAME = str(Path("data") / "prices.sqlite")
HANDLER_CACHE_DB_FILENAME  = str(Path("data") / "handler_cache.3.sqlite")
HELP_FILENAME = 'readme.md'
