import os
from dotenv import load_dotenv

load_dotenv()

# Existing config (MONITORED_DOMAINS, PERIOD_OPTIONS, etc...)

AHREFS_API_BASE_URL = os.getenv("AHREFS_API_BASE_URL", "https://api.ahrefs.com/v3")
AHREFS_API_TOKEN = os.getenv("AHREFS_API_TOKEN")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

# Period options for the dashboard
PERIOD_OPTIONS = ["month", "year"]

# Domains to monitor - each entry should have 'domain' and 'country' keys
# Optional: 'label' (display name) and 'flag' (emoji flag)
MONITORED_DOMAINS = [
    {
        "domain": "gambling.com",
        "country": "AU",
        "label": "Gambling.com",
        "flag": "🇦🇺"
    },
    # Add more domains as needed:
    # {
    #     "domain": "example.com",
    #     "country": "US",
    #     "label": "Example Domain",
    #     "flag": "🇺🇸"
    # },
]
