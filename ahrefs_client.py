# ahrefs_client.py
import os
from typing import Any, Dict, Optional

import requests

from config import AHREFS_API_BASE_URL, AHREFS_API_TOKEN, API_TIMEOUT


class AhrefsClient:
    """
    Very small wrapper around the Ahrefs v3 API.

    Right now we only use Site Explorer > Overview to get:
    - organic_traffic
    - organic_keywords
    - paid_traffic
    - paid_keywords
    - referring domains
    - DR (authority)
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.api_key = api_key or AHREFS_API_TOKEN
        self.base_url = (base_url or AHREFS_API_BASE_URL).rstrip("/")

        if not self.api_key:
            raise RuntimeError(
                "Ahrefs API key is not configured. "
                "Set A_HREFS_API_TOKEN in your environment or .env file."
            )

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _headers(self) -> Dict[str, str]:
        # v3 uses Bearer token in Authorization header
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = requests.get(url, headers=self._headers(), params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    # public methods used by stats_service
    # ------------------------------------------------------------------ #
    def overview(self, target: str, country: Optional[str] = None) -> Dict[str, Any]:
        """
        Call Ahrefs Site Explorer 'overview' report.

        Docs pattern (v3):
        https://api.ahrefs.com/v3/site-explorer/overview?target=example.com

        Some plans / configs may support a 'country' parameter; we pass it
        only if provided.
        """
        params: Dict[str, Any] = {"target": target}

        # If your account supports per-country overview, you can uncomment:
        if country:
            params["country"] = country

        return self._get("site-explorer/overview", params)
