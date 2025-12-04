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

# Changes timeframe options (similar to Ahrefs "Changes" dropdown)
# Maps display name to days
CHANGES_OPTIONS = {
    "Don't show": None,
    "Last 24 hours": 1,
    "Last 7 days": 7,
    "Last month": 30,
    "Last 3 months": 90,
    "Last 6 months": 180,
    "Last year": 365,
    "Last 2 years": 730,
    "Last 5 years": 1825,
}
CHANGES_OPTIONS_LIST = list(CHANGES_OPTIONS.keys())

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
    {
        "domain": "www.gambling.com/uk",
        "country": "GB",
        "label": "Gambling.com UK",
        "flag": "🇬🇧"
    },
    {
        "domain": "www.gambling.com/us",
        "country": "US",
        "label": "Gambling.com US",
        "flag": "🇺🇸"
    },
    {
        "domain": "www.gambling.com/nz",
        "country": "NZ",
        "label": "Gambling.com NZ",
        "flag": "🇳🇿"
    },
    {
        "domain": "www.gambling.com/ie",
        "country": "IE",
        "label": "Gambling.com IE",
        "flag": "🇮🇪"
    },
]
