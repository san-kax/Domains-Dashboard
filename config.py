import os
from dotenv import load_dotenv

load_dotenv()

# Existing config (MONITORED_DOMAINS, PERIOD_OPTIONS, etc...)

AHREFS_API_BASE_URL = os.getenv("AHREFS_API_BASE_URL", "https://api.ahrefs.com/v3")
AHREFS_API_TOKEN = os.getenv("AHREFS_API_TOKEN")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
