import os
from dotenv import load_dotenv

load_dotenv()

SCDP_URL = os.getenv("SCDP_URL", "https://www2.scdp.gov.br/novoscdp/")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
DELAY_MIN = float(os.getenv("DELAY_MIN", "1"))
DELAY_MAX = float(os.getenv("DELAY_MAX", "3"))
TESSERACT_PATH = os.getenv("TESSERACT_PATH", "/opt/homebrew/bin/tesseract")
DB_PATH = os.getenv("DB_PATH", "scdp_bot.db")
