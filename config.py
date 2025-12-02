import os
from dotenv import load_dotenv

load_dotenv()

# Try to import streamlit for secrets (if running in Streamlit)
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    st = None

# Helper to get config from env or Streamlit secrets
def _get_config(key: str, default: str = "") -> str:
    """Get config value from Streamlit secrets (if available) or environment variable."""
    if HAS_STREAMLIT and st is not None:
        try:
            # Check if Streamlit is initialized and has secrets
            if hasattr(st, "secrets"):
                value = st.secrets.get(key, "")
                if value:
                    return value
        except (AttributeError, RuntimeError, Exception):
            # Streamlit not initialized or secrets not available
            pass
    return os.getenv(key, default)

# Existing config (MONITORED_DOMAINS, PERIOD_OPTIONS, etc...)

AHREFS_API_BASE_URL = _get_config("AHREFS_API_BASE_URL", "https://api.ahrefs.com/v3")
# Check both naming conventions (with and without underscore) for backward compatibility
AHREFS_API_TOKEN = _get_config("AHREFS_API_TOKEN", "") or _get_config("A_HREFS_API_TOKEN", "")
API_TIMEOUT = int(_get_config("API_TIMEOUT", "30"))

# Period options for the dashboard
PERIOD_OPTIONS = ["month", "year"]

# Domains to monitor - each entry should have 'domain' and 'country' keys
# Optional: 'label' (display name) and 'flag' (emoji flag)
# Note: Use full domain paths (e.g., www.gambling.com/au) for country-specific data
MONITORED_DOMAINS = [
    {
        "domain": "www.gambling.com/au",
        "country": "AU",
        "label": "Gambling.com AU",
        "flag": "🇦🇺"
    },
    {
        "domain": "www.gambling.com/ca",
        "country": "CA",
        "label": "Gambling.com CA",
        "flag": "🇨🇦"
    },
    # Add more domains as needed:
    # {
    #     "domain": "www.example.com/us",
    #     "country": "US",
    #     "label": "Example Domain US",
    #     "flag": "🇺🇸"
    # },
]
