# ahrefs_client.py

import os
from datetime import date
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv

load_dotenv()

A_HREFS_API_TOKEN = os.getenv("A_HREFS_API_TOKEN")
BASE_URL = "https://api.ahrefs.com/v3"  # v3 base URL for Enterprise


class AhrefsClient:
    """
    Thin wrapper around Ahrefs API v3.
    Adjust endpoints/params to match your account setup.
    """

    def __init__(self, token: str = None):
        self.token = token or A_HREFS_API_TOKEN
        if not self.token:
            raise ValueError(
                "A_HREFS_API_TOKEN not set. Set it in environment or .env or Streamlit secrets."
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    # ----------- POSITIONS (organic/paid) ----------- #

    def positions_overview(
        self,
        domain: str,
        country: str,
        date_from: date,
        date_to: date,
    ) -> Dict[str, Any]:
        """
        Fetch organic & paid metrics over time for a domain+country.

        NOTE:
        - This uses a hypothetical /seo-metrics/positions-overview endpoint.
        - You may decide to use /v3/rank-tracker/positions-overview or
          /v3/seo-metrics/traffic-overview depending on your Ahrefs docs.

        Replace URL and params according to your v3 docs.
        """
        url = f"{BASE_URL}/seo-metrics/positions-overview"
        params = {
            "target": domain,
            "target_type": "domain",
            "country": country,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            # Request both organic and paid metrics if available
            "metrics": "organic_keywords,organic_traffic,paid_keywords,paid_traffic",
            "interval": "day",  # or week/month depending on what you prefer
        }

        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    # ----------- BACKLINKS / REFERRING DOMAINS ----------- #

    def backlinks_overview(
        self,
        domain: str,
        date_from: date,
        date_to: date,
    ) -> Dict[str, Any]:
        """
        Fetch referring domains over time.

        You might use something like /seo-metrics/backlinks-overview or
        another v3 endpoint exposed to you.
        """
        url = f"{BASE_URL}/seo-metrics/backlinks-overview"
        params = {
            "target": domain,
            "target_type": "domain",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "metrics": "refdomains",
            "interval": "day",
        }

        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    # ----------- BATCH DOMAIN METRICS (DR / Authority Score) ----------- #

    def batch_domain_metrics(self, domains: List[str]) -> Dict[str, Any]:
        """
        Uses /v3/batch-analysis/batch-analysis which you already tested.

        Make sure 'domain_rating' is among the metrics in your docs.
        """
        url = f"{BASE_URL}/batch-analysis/batch-analysis"
        payload = {
            "targets": domains,
            "metrics": ["domain_rating"],
        }

        response = requests.post(url, headers=self._headers(), json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
