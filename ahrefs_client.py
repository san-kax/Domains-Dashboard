# ahrefs_client.py
import os
import time
from typing import Any, Dict, List, Optional

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

    def _get(self, path: str, params: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
        """
        Make GET request with retry logic for transient errors (500, 502, 503, 504).
        
        Args:
            path: API endpoint path
            params: Query parameters
            max_retries: Maximum number of retry attempts for 5xx errors (default: 2)
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        
        # Retry logic for 5xx server errors (transient errors)
        last_exception = None
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                resp = requests.get(url, headers=self._headers(), params=params, timeout=API_TIMEOUT)
                
                # If successful, return immediately
                if resp.ok:
                    return resp.json()
                
                # Handle errors
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
                elif resp.status_code in (500, 502, 503, 504):
                    # Transient server errors - retry with exponential backoff
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                        time.sleep(wait_time)
                        continue  # Retry the request
                    else:
                        error_msg += " (Server error - retries exhausted. This may be a temporary Ahrefs API issue.)"
                
                # For non-retryable errors or after max retries, raise the error
                last_exception = requests.HTTPError(error_msg, response=resp)
                raise last_exception
                
            except requests.HTTPError as e:
                # Re-raise if it's not a retryable error or we've exhausted retries
                if e.response and e.response.status_code in (500, 502, 503, 504) and attempt < max_retries:
                    wait_time = (2 ** attempt) * 0.5
                    time.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                # For other exceptions (network errors, etc.), retry once
                if attempt < max_retries:
                    wait_time = (2 ** attempt) * 0.5
                    time.sleep(wait_time)
                    last_exception = e
                    continue
                raise
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        raise requests.HTTPError("Request failed after retries", response=None)

    # ------------------------------------------------------------------ #
    # public methods used by stats_service
    # ------------------------------------------------------------------ #
    def overview(self, target: str, country: Optional[str] = None, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch overview metrics using the correct Ahrefs API v3 endpoints to match Ahrefs UI exactly.
        
        Uses the following endpoints (as per Ahrefs UI):
        - /v3/site-explorer/organic/keywords-overview for organic keywords
        - /v3/site-explorer/organic/traffic-overview for organic traffic
        - /v3/backlinks/refdomains/refdomains-overview for referring domains
        - /v3/site-explorer/domain-rating for DR (or /v3/backlinks/metrics)
        
        Args:
            target: Domain or URL to analyze (e.g., "www.gambling.com/us")
            country: Optional country code (not used - we use "all" to match UI)
            date: Optional date string in YYYY-MM-DD format. If not provided, uses yesterday's date.
        """
        # CRITICAL: Initialize metrics dict FIRST - before ANY imports or other code
        # This MUST be the first executable line to prevent UnboundLocalError
        metrics: Dict[str, Any] = {}
        errors: List[str] = []
        
        from datetime import datetime, timedelta
        
        # Handle target format - remove trailing slash if present (Ahrefs API doesn't need it)
        target = target.rstrip('/')
        
        # Use provided date or default to yesterday (Ahrefs typically shows data up to yesterday)
        if date:
            date_str = date
        else:
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            date_str = yesterday.strftime("%Y-%m-%d")
        
        # CRITICAL: Use "path" mode (not "prefix" or "domain") to match Ahrefs UI exactly
        # Ahrefs UI uses "Path" mode by default, which corresponds to mode="path" in API
        # If target has a path (e.g., www.gambling.com/us), use "path" mode
        # Otherwise, use "domain" mode
        if "/" in target and target.count("/") >= 1:  # Has path (e.g., www.gambling.com/us)
            mode = "path"  # CRITICAL: Must be "path" to match Ahrefs UI
        else:
            mode = "domain"  # For domain-only queries
        
        # Base parameters for all endpoints
        # country="all" or omit it (Ahrefs treats empty as all-locations) to match "All Locations" in UI
        base_params: Dict[str, Any] = {
            "target": target,
            "mode": mode,  # CRITICAL: "path" mode
            "date": date_str
        }
        
        # For organic endpoints, add country="all" to match "All Locations" in Ahrefs UI
        organic_params: Dict[str, Any] = {
            **base_params,
            "country": "all"  # Match "All Locations" in Ahrefs UI
        }
        
        # Store parameters for debugging
        metrics["_api_params_base"] = base_params
        metrics["_api_params_organic"] = organic_params
        
        # 1. Domain Rating (DR) - from domain-rating endpoint
        try:
            dr_params = {**base_params, "protocol": "both"}
            dr_response = self._get("site-explorer/domain-rating", dr_params)
            metrics["_raw_dr_response"] = dr_response
            
            if isinstance(dr_response, dict):
                if "domain_rating" in dr_response:
                    inner = dr_response["domain_rating"]
                    if isinstance(inner, dict):
                        dr_value = inner.get("domain_rating") or inner.get("dr") or inner.get("value")
                    else:
                        dr_value = inner
                else:
                    dr_value = dr_response.get("domain_rating") or dr_response.get("dr") or dr_response.get("value")
                
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
        
        # 2. Organic Keywords - use correct endpoint: /v3/site-explorer/organic/keywords-overview
        try:
            keywords_response = self._get("site-explorer/organic/keywords-overview", organic_params)
            metrics["_raw_keywords_response"] = keywords_response
            
            organic_kw = None
            if isinstance(keywords_response, dict):
                # Try various response structures
                data = keywords_response.get("metrics") or keywords_response.get("data") or keywords_response
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                if isinstance(data, dict):
                    # Look for keywords count
                    organic_kw = (data.get("keywords") or data.get("organic_keywords") or 
                                 data.get("org_keywords") or data.get("keywords_count") or
                                 data.get("count"))
            
            metrics["organic_keywords"] = _safe_int(organic_kw) if organic_kw is not None else 0
        except Exception as e:
            errors.append(f"Organic Keywords: {str(e)}")
            metrics["organic_keywords"] = 0
        
        # 3. Organic Traffic - use correct endpoint: /v3/site-explorer/organic/traffic-overview
        try:
            traffic_response = self._get("site-explorer/organic/traffic-overview", organic_params)
            metrics["_raw_traffic_response"] = traffic_response
            
            organic_tr = None
            if isinstance(traffic_response, dict):
                # Try various response structures
                data = traffic_response.get("metrics") or traffic_response.get("data") or traffic_response
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                if isinstance(data, dict):
                    # Look for traffic count
                    organic_tr = (data.get("traffic") or data.get("organic_traffic") or 
                                  data.get("org_traffic") or data.get("traffic_count") or
                                  data.get("visits") or data.get("organic_visits"))
            
            metrics["organic_traffic"] = _safe_int(organic_tr) if organic_tr is not None else 0
        except Exception as e:
            errors.append(f"Organic Traffic: {str(e)}")
            metrics["organic_traffic"] = 0
        
        # 4. Referring Domains - use correct endpoint: /v3/backlinks/refdomains/refdomains-overview
        # CRITICAL: Must include refdomains_mode="live" to match Ahrefs UI
        try:
            refdomains_params = {
                **base_params,
                "refdomains_mode": "live"  # CRITICAL: Must be "live" to match Ahrefs UI
            }
            refdomains_response = self._get("backlinks/refdomains/refdomains-overview", refdomains_params)
            metrics["_raw_refdomains_response"] = refdomains_response
            metrics["_api_params_refdomains"] = refdomains_params
            
            ref_doms = None
            if isinstance(refdomains_response, dict):
                # Try various response structures
                data = refdomains_response.get("metrics") or refdomains_response.get("data") or refdomains_response
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                if isinstance(data, dict):
                    # Look for referring domains count
                    ref_doms = (data.get("refdomains") or data.get("referring_domains") or 
                               data.get("ref_domains") or data.get("live_refdomains") or
                               data.get("count") or data.get("refdomains_count"))
            
            metrics["ref_domains"] = _safe_int(ref_doms) if ref_doms is not None else 0
        except Exception as e:
            errors.append(f"Referring Domains: {str(e)}")
            metrics["ref_domains"] = 0
        
        # Set defaults for paid metrics (not needed but keeping structure)
        if "paid_keywords" not in metrics:
            metrics["paid_keywords"] = 0
        if "paid_traffic" not in metrics:
            metrics["paid_traffic"] = 0
        
        # Ensure all required keys exist
        if "domain_rating" not in metrics:
            metrics["domain_rating"] = 0
        if "organic_keywords" not in metrics:
            metrics["organic_keywords"] = 0
        if "organic_traffic" not in metrics:
            metrics["organic_traffic"] = 0
        if "ref_domains" not in metrics:
            metrics["ref_domains"] = 0
        
        # Store errors in metrics for debugging (optional)
        if errors:
            metrics["_errors"] = errors
        
        return metrics
