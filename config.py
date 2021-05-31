import secrets
from pathlib import Path

TG_TOKEN = secrets.TG_TOKEN
CC_API_KEY = secrets.CC_API_KEY
DB_FILENAME = Path("data") / "db.sqlite"
PRICES_DB_FILENAME = Path("data") / "prices.sqlite"
HELP_FILENAME = 'help.md'
