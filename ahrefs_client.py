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
                "Set AHREFS_API_TOKEN in your environment or .env file."
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
        
        # Provide detailed error information
        if not resp.ok:
            error_msg = f"Ahrefs API error: HTTP {resp.status_code}"
            try:
                error_data = resp.json()
                if isinstance(error_data, dict):
                    error_detail = error_data.get("error", error_data.get("message", str(error_data)))
                    error_msg += f" - {error_detail}"
                else:
                    error_msg += f" - {error_data}"
            except Exception:
                error_msg += f" - {resp.text[:200]}"
            
            # Add helpful context based on status code
            if resp.status_code == 401:
                error_msg += " (Invalid API token. Please check your A_HREFS_API_TOKEN in Streamlit secrets.)"
            elif resp.status_code == 403:
                error_msg += " (API token doesn't have permission for this endpoint or rate limit exceeded.)"
            elif resp.status_code == 404:
                error_msg += " (API endpoint not found. Please check the API documentation.)"
            elif resp.status_code == 429:
                error_msg += " (Rate limit exceeded. Please try again later.)"
            
            raise requests.HTTPError(error_msg, response=resp)
        
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
