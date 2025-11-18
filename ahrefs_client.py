# ahrefs_client.py
import os
from typing import Any, Dict, Optional

import requests

from config import AHREFS_API_BASE_URL, AHREFS_API_TOKEN, API_TIMEOUT


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


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
        Fetch overview metrics using the correct Ahrefs API v3 endpoints.
        
        Uses the following endpoints:
        - site-explorer/domain-rating for DR
        - site-explorer/metrics for organic keywords, organic traffic, referring domains
        - site-explorer/backlinks-stats for backlinks count
        """
        from datetime import datetime, timedelta
        
        # Ensure target ends with / as required by Ahrefs API
        if not target.endswith('/'):
            target = f"{target}/"
        
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")
        
        # Base parameters for metrics endpoint
        # Note: country parameter is NOT supported for metrics endpoint (causes HTTP 400)
        metrics_params: Dict[str, Any] = {
            "target": target,
            "date": date_str,
            "mode": "subdomains",
            "protocol": "both",
            "volume_mode": "monthly"
        }
        
        # Base parameters for domain-rating endpoint
        dr_params: Dict[str, Any] = {
            "target": target,
            "date": date_str,
            "protocol": "both"
        }
        # Note: country parameter may not be supported for domain-rating either
        
        # Base parameters for backlinks-stats endpoint
        backlinks_params: Dict[str, Any] = {
            "target": target,
            "date": date_str,
            "mode": "subdomains",
            "protocol": "both"
        }
        # Note: country parameter may not be supported for backlinks-stats either
        
        metrics = {}
        errors = []
        
        # 1. Domain Rating (DR) - from domain-rating endpoint
        try:
            dr_response = self._get("site-explorer/domain-rating", dr_params)
            # Store raw response for debugging
            metrics["_raw_dr_response"] = dr_response
            
            if isinstance(dr_response, dict):
                # Handle nested structure: {"domain_rating": {"domain_rating": 78, ...}}
                if "domain_rating" in dr_response:
                    inner = dr_response["domain_rating"]
                    if isinstance(inner, dict):
                        # Nested structure - extract from inner dict
                        dr_value = inner.get("domain_rating") or inner.get("dr") or inner.get("value")
                    else:
                        # Direct value
                        dr_value = inner
                else:
                    # Try flat structure
                    dr_value = dr_response.get("domain_rating") or dr_response.get("dr") or dr_response.get("value")
                
                # Convert to int only if it's a number
                if dr_value is not None:
                    if isinstance(dr_value, (int, float)):
                        metrics["domain_rating"] = int(dr_value)
                    elif isinstance(dr_value, str) and dr_value.isdigit():
                        metrics["domain_rating"] = int(dr_value)
                    else:
                        metrics["domain_rating"] = 0
                else:
                    metrics["domain_rating"] = 0
            elif isinstance(dr_response, (int, float)):
                metrics["domain_rating"] = int(dr_response)
            else:
                metrics["domain_rating"] = 0
        except Exception as e:
            errors.append(f"Domain Rating: {str(e)}")
            metrics["domain_rating"] = 0
        
        # 2. Main metrics endpoint - contains organic keywords, organic traffic, referring domains
        # IMPORTANT: Do NOT pass country parameter - it causes HTTP 400 error
        try:
            # Ensure country is not in params (in case it was added elsewhere)
            clean_metrics_params = {k: v for k, v in metrics_params.items() if k != "country"}
            metrics_response = self._get("site-explorer/metrics", clean_metrics_params)
            if isinstance(metrics_response, dict):
                # Debug: Store raw response for troubleshooting
                metrics["_raw_metrics_response"] = metrics_response
                
                # Extract metrics - Ahrefs API returns: {"metrics": {"org_keywords": ..., "org_traffic": ...}}
                data = metrics_response.get("metrics") or metrics_response.get("data") or metrics_response
                
                # If data is a list, get first item
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                
                # Organic Keywords - Ahrefs uses "org_keywords" not "organic_keywords"
                organic_kw = (
                    data.get("org_keywords")  # Primary key from Ahrefs API
                    or data.get("organic_keywords")
                    or data.get("organicKeywords")
                    or data.get("keywords")
                    or 0
                )
                metrics["organic_keywords"] = _safe_int(organic_kw)
                
                # Organic Traffic - Ahrefs uses "org_traffic" not "organic_traffic"
                organic_tr = (
                    data.get("org_traffic")  # Primary key from Ahrefs API
                    or data.get("organic_traffic")
                    or data.get("organicTraffic")
                    or data.get("traffic")
                    or 0
                )
                metrics["organic_traffic"] = _safe_int(organic_tr)
                
                # Referring Domains - not in metrics endpoint, need to get from backlinks-stats
                # Will be set below from backlinks-stats endpoint
                metrics["ref_domains"] = 0
            else:
                metrics["organic_keywords"] = 0
                metrics["organic_traffic"] = 0
                metrics["ref_domains"] = 0
        except Exception as e:
            errors.append(f"Metrics endpoint: {str(e)}")
            metrics["organic_keywords"] = 0
            metrics["organic_traffic"] = 0
            metrics["ref_domains"] = 0
        
        # 3. Backlinks Stats - for backlinks count and referring domains
        try:
            # Ensure country is not in params
            clean_backlinks_params = {k: v for k, v in backlinks_params.items() if k != "country"}
            backlinks_response = self._get("site-explorer/backlinks-stats", clean_backlinks_params)
            if isinstance(backlinks_response, dict):
                # Ahrefs API structure might be: {"backlinks_stats": {...}} or {"data": {...}}
                data = backlinks_response.get("backlinks_stats") or backlinks_response.get("data") or backlinks_response
                
                # Extract referring domains - try different possible keys
                ref_doms = _safe_int(
                    data.get("refdomains")
                    or data.get("referring_domains")
                    or data.get("referringDomains")
                    or data.get("ref_domains")
                    or 0
                )
                if ref_doms > 0:
                    metrics["ref_domains"] = ref_doms
                
                # Extract backlinks count if available
                backlinks_count = _safe_int(
                    data.get("backlinks")
                    or data.get("backlinks_count")
                    or data.get("total_backlinks")
                    or 0
                )
                if backlinks_count > 0:
                    metrics["backlinks"] = backlinks_count
        except Exception as e:
            # Backlinks stats is optional, so we don't add to errors unless it's critical
            pass
        
        # Set defaults for paid metrics (not needed but keeping structure)
        metrics["paid_keywords"] = 0
        metrics["paid_traffic"] = 0
        
        # Store errors in metrics for debugging (optional)
        if errors:
            metrics["_errors"] = errors
        
        return metrics
