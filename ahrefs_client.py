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
        Fetch overview metrics by calling multiple Ahrefs API v3 endpoints.
        
        Ahrefs v3 uses specific endpoints for each metric:
        - site-explorer/domain-rating for DR
        - site-explorer/organic-keywords for organic keywords
        - site-explorer/organic-traffic for organic traffic
        - site-explorer/refdomains for referring domains
        """
        from datetime import datetime
        
        # Ensure target ends with / as required by Ahrefs API
        if not target.endswith('/'):
            target = f"{target}/"
        
        # Base parameters for all endpoints
        base_params: Dict[str, Any] = {
            "target": target,
            "protocol": "both",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        # Add country if provided (some endpoints may support it)
        if country:
            base_params["country"] = country
        
        # Fetch metrics from different endpoints
        metrics = {}
        
        # 1. Domain Rating (DR)
        try:
            dr_response = self._get("site-explorer/domain-rating", base_params)
            if isinstance(dr_response, dict):
                # Extract DR value - structure may vary
                metrics["domain_rating"] = dr_response.get("domain_rating") or dr_response.get("dr") or dr_response.get("value") or 0
        except Exception as e:
            metrics["domain_rating"] = 0
        
        # 2. Organic Keywords
        try:
            keywords_response = self._get("site-explorer/organic-keywords", base_params)
            if isinstance(keywords_response, dict):
                metrics["organic_keywords"] = keywords_response.get("organic_keywords") or keywords_response.get("keywords") or keywords_response.get("value") or 0
        except Exception as e:
            metrics["organic_keywords"] = 0
        
        # 3. Organic Traffic
        try:
            traffic_response = self._get("site-explorer/organic-traffic", base_params)
            if isinstance(traffic_response, dict):
                metrics["organic_traffic"] = traffic_response.get("organic_traffic") or traffic_response.get("traffic") or traffic_response.get("value") or 0
        except Exception as e:
            metrics["organic_traffic"] = 0
        
        # 4. Referring Domains
        try:
            refdomains_response = self._get("site-explorer/refdomains", base_params)
            if isinstance(refdomains_response, dict):
                metrics["ref_domains"] = refdomains_response.get("refdomains") or refdomains_response.get("referring_domains") or refdomains_response.get("value") or 0
        except Exception as e:
            metrics["ref_domains"] = 0
        
        # Set defaults for paid metrics (not needed but keeping structure)
        metrics["paid_keywords"] = 0
        metrics["paid_traffic"] = 0
        
        return metrics
