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
        
        # Handle target format - Ahrefs API expects URLs with trailing slash
        # If target is a path like "www.gambling.com/au", ensure it has trailing slash
        # If target is just a domain, add trailing slash
        if not target.endswith('/'):
            target = f"{target}/"
        
        # Note: Ahrefs API accepts domain/path format without protocol
        # For path-specific queries (e.g., www.gambling.com/au), the API will return
        # data specific to that path when using appropriate mode parameter
        # If results don't match expected values, try adding protocol: https://{target}
        
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")
        
        # Determine mode based on target format
        # If target contains a path (e.g., www.gambling.com/au), use "prefix" mode
        # If target is just a domain, use "subdomains" mode
        # "exact" mode is for exact URL matching
        if "/" in target and target.count("/") > 1:  # Has path (e.g., www.gambling.com/au/)
            mode = "prefix"  # Get data for this path and subpaths
        else:
            mode = "subdomains"  # Get data for all subdomains
        
        # Base parameters for metrics endpoint
        # Note: country parameter is NOT supported for metrics endpoint (causes HTTP 400)
        metrics_params: Dict[str, Any] = {
            "target": target,
            "date": date_str,
            "mode": mode,
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
        # Use the same mode as metrics endpoint for consistency
        backlinks_params: Dict[str, Any] = {
            "target": target,
            "date": date_str,
            "mode": mode,  # Use the same mode determined above
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
                # Get the inner metrics dict
                data = metrics_response.get("metrics")
                if data is None:
                    data = metrics_response.get("data")
                if data is None:
                    data = metrics_response
                
                # If data is a list, get first item
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                
                # Ensure data is a dict
                if not isinstance(data, dict):
                    data = {}
                
                # Debug: Store extracted data for troubleshooting
                metrics["_extracted_data"] = data
                
                # Organic Keywords - Ahrefs API v3 uses various key names
                # Try multiple variations to handle different response structures
                organic_kw = None
                for key in ["org_keywords", "organic_keywords", "organicKeywords", "keywords", 
                           "organic_keywords_count", "org_keywords_count"]:
                    if key in data:
                        organic_kw = data[key]
                        break
                
                # If still None, check if it's nested in another structure
                if organic_kw is None:
                    # Sometimes the data might be in a nested structure like {"organic": {"keywords": ...}}
                    if "organic" in data and isinstance(data["organic"], dict):
                        organic_kw = data["organic"].get("keywords") or data["organic"].get("keywords_count")
                
                metrics["organic_keywords"] = _safe_int(organic_kw) if organic_kw is not None else 0
                
                # Organic Traffic - Ahrefs API v3 uses various key names
                organic_tr = None
                for key in ["org_traffic", "organic_traffic", "organicTraffic", "traffic",
                           "organic_traffic_count", "org_traffic_count"]:
                    if key in data:
                        organic_tr = data[key]
                        break
                
                # If still None, check if it's nested in another structure
                if organic_tr is None:
                    # Sometimes the data might be in a nested structure like {"organic": {"traffic": ...}}
                    if "organic" in data and isinstance(data["organic"], dict):
                        organic_tr = data["organic"].get("traffic") or data["organic"].get("traffic_count")
                
                metrics["organic_traffic"] = _safe_int(organic_tr) if organic_tr is not None else 0
                
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
            
            # Store raw response for debugging
            metrics["_raw_backlinks_response"] = backlinks_response
            
            if isinstance(backlinks_response, dict):
                # Ahrefs API v3 response structure: {"metrics": {"live_refdomains": 32010, ...}}
                # Extract referring domains from the response
                ref_doms = None
                
                # Priority 1: Check if "metrics" key exists directly in response (most common)
                # Response structure: {"metrics": {"live_refdomains": 32010, ...}}
                if "metrics" in backlinks_response:
                    metrics_dict = backlinks_response["metrics"]
                    if isinstance(metrics_dict, dict):
                        # Try "live_refdomains" first (Ahrefs API v3 format)
                        if "live_refdomains" in metrics_dict:
                            ref_doms = metrics_dict["live_refdomains"]
                        # Fallback to other key names
                        elif "refdomains" in metrics_dict:
                            ref_doms = metrics_dict["refdomains"]
                        elif "referring_domains" in metrics_dict:
                            ref_doms = metrics_dict["referring_domains"]
                        elif "ref_domains" in metrics_dict:
                            ref_doms = metrics_dict["ref_domains"]
                
                # Priority 2: Check nested structures (backlinks_stats, data)
                if ref_doms is None:
                    data = backlinks_response.get("backlinks_stats") or backlinks_response.get("data")
                    if isinstance(data, dict):
                        if "metrics" in data and isinstance(data["metrics"], dict):
                            metrics_dict = data["metrics"]
                            if "live_refdomains" in metrics_dict:
                                ref_doms = metrics_dict["live_refdomains"]
                            elif "refdomains" in metrics_dict:
                                ref_doms = metrics_dict["refdomains"]
                        # Check directly in data dict
                        elif "live_refdomains" in data:
                            ref_doms = data["live_refdomains"]
                        elif "refdomains" in data:
                            ref_doms = data["refdomains"]
                
                # Priority 3: Check top-level response (flat structure)
                if ref_doms is None:
                    if "live_refdomains" in backlinks_response:
                        ref_doms = backlinks_response["live_refdomains"]
                    elif "refdomains" in backlinks_response:
                        ref_doms = backlinks_response["refdomains"]
                
                # Update ref_domains if we found a value (always update, even if it was set to 0 earlier)
                if ref_doms is not None:
                    ref_doms_int = _safe_int(ref_doms)
                    metrics["ref_domains"] = ref_doms_int
                    # Store for debugging
                    metrics["_extracted_ref_domains"] = ref_doms
                    metrics["_extracted_ref_domains_int"] = ref_doms_int
                    metrics["_extracted_ref_domains_source"] = "backlinks-stats"
                elif "ref_domains" not in metrics:
                    # Only set to 0 if it wasn't already set
                    metrics["ref_domains"] = 0
                
                # Extract backlinks count if available
                backlinks_count = None
                # Check in metrics dict first
                if "metrics" in backlinks_response and isinstance(backlinks_response["metrics"], dict):
                    metrics_dict = backlinks_response["metrics"]
                    if "live" in metrics_dict:
                        backlinks_count = metrics_dict["live"]
                    elif "backlinks" in metrics_dict:
                        backlinks_count = metrics_dict["backlinks"]
                
                # Fallback to top-level
                if backlinks_count is None:
                    backlinks_count = backlinks_response.get("backlinks") or backlinks_response.get("backlinks_count") or 0
                
                if backlinks_count and _safe_int(backlinks_count) > 0:
                    metrics["backlinks"] = _safe_int(backlinks_count)
        except Exception as e:
            # Backlinks stats is optional, so we don't add to errors unless it's critical
            # But store the error for debugging
            errors.append(f"Backlinks Stats: {str(e)}")
            # Don't overwrite ref_domains if it was already set from metrics endpoint
            if "ref_domains" not in metrics:
                metrics["ref_domains"] = 0
        
        # Set defaults for paid metrics (not needed but keeping structure)
        metrics["paid_keywords"] = 0
        metrics["paid_traffic"] = 0
        
        # Store errors in metrics for debugging (optional)
        if errors:
            metrics["_errors"] = errors
        
        return metrics
