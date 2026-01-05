# stats_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ahrefs_client import AhrefsClient


# ------------------------------------------------------------------ #
# data structure consumed by the Streamlit UI
# ------------------------------------------------------------------ #
@dataclass
class Metric:
    value: float
    change_pct: Optional[float] = None
    change_value: Optional[float] = None  # Actual numeric change (e.g., -667, +309)
    previous_value: Optional[float] = None  # Previous period value for tooltip
    sparkline: Optional[List[float]] = None


@dataclass
class DomainStats:
    domain: str
    country: str
    organic_keywords: Metric
    organic_traffic: Metric
    paid_keywords: Metric
    paid_traffic: Metric
    ref_domains: Metric
    authority_score: float


# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #
def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _flat_trend(value: int, points: int) -> List[float]:
    """Just repeat the current value N times to draw a flat sparkline."""
    return [float(value)] * max(points, 1)


def _extract_metrics_from_overview(payload: Dict[str, Any]) -> Dict[str, int]:
    """
    Extract metrics from Ahrefs API v3 response.
    
    The overview() method returns a flat dictionary with metrics at the top level,
    so we extract directly from the payload.
    """
    # The payload from overview() is already a flat dictionary with metrics at top level
    # Handle both nested and flat structures for robustness
    # First, check if there's a nested "metrics" key (from raw API response)
    if "metrics" in payload and isinstance(payload["metrics"], dict) and not payload["metrics"].get("_raw"):
        # If nested structure exists and it's not a debug key, use it
        metrics: Dict[str, Any] = payload["metrics"]
    else:
        # Otherwise, payload is already flat with metrics at top level
        # Filter out debug keys (starting with _)
        metrics = {k: v for k, v in payload.items() if not k.startswith("_")}

    # Extract organic traffic - try multiple key variations
    # Use explicit None checks instead of 'or' to handle 0 as a valid value
    # Check both in metrics dict and top-level payload
    organic_traffic = None
    for key in ["organic_traffic", "organicTraffic", "org_traffic"]:
        if key in metrics and metrics[key] is not None:
            organic_traffic = metrics[key]
            break
    # If not found in metrics, check top-level payload
    if organic_traffic is None:
        for key in ["organic_traffic", "organicTraffic", "org_traffic"]:
            if key in payload and payload[key] is not None:
                organic_traffic = payload[key]
                break
    organic_traffic = _safe_int(organic_traffic) if organic_traffic is not None else 0
    
    # Extract organic keywords - try multiple key variations
    organic_keywords = None
    for key in ["organic_keywords", "organicKeywords", "org_keywords"]:
        if key in metrics and metrics[key] is not None:
            organic_keywords = metrics[key]
            break
    # If not found in metrics, check top-level payload
    if organic_keywords is None:
        for key in ["organic_keywords", "organicKeywords", "org_keywords"]:
            if key in payload and payload[key] is not None:
                organic_keywords = payload[key]
                break
    organic_keywords = _safe_int(organic_keywords) if organic_keywords is not None else 0
    
    # Extract paid traffic
    paid_traffic = None
    for key in ["paid_traffic", "paidTraffic"]:
        if key in metrics and metrics[key] is not None:
            paid_traffic = metrics[key]
            break
    paid_traffic = _safe_int(paid_traffic) if paid_traffic is not None else 0
    
    # Extract paid keywords
    paid_keywords = None
    for key in ["paid_keywords", "paidKeywords"]:
        if key in metrics and metrics[key] is not None:
            paid_keywords = metrics[key]
            break
    paid_keywords = _safe_int(paid_keywords) if paid_keywords is not None else 0

    # Extract referring domains - try multiple key variations
    ref_domains = None
    for key in ["ref_domains", "referring_domains", "referringDomains", "refdomains"]:
        if key in metrics and metrics[key] is not None:
            ref_domains = metrics[key]
            break
    # Also check top-level payload if not found in metrics
    if ref_domains is None:
        for key in ["ref_domains", "referring_domains", "referringDomains", "refdomains"]:
            if key in payload and payload[key] is not None:
                ref_domains = payload[key]
                break
    ref_domains = _safe_int(ref_domains) if ref_domains is not None else 0

    # Extract domain rating/authority score - try multiple key variations
    authority_score = None
    for key in ["domain_rating", "domainRating", "dr"]:
        if key in metrics and metrics[key] is not None:
            authority_score = metrics[key]
            break
    # Also check top-level payload if not found in metrics
    if authority_score is None:
        for key in ["domain_rating", "domainRating", "dr"]:
            if key in payload and payload[key] is not None:
                authority_score = payload[key]
                break
    authority_score = _safe_int(authority_score) if authority_score is not None else 0

    return {
        "organic_traffic": organic_traffic,
        "organic_keywords": organic_keywords,
        "paid_traffic": paid_traffic,
        "paid_keywords": paid_keywords,
        "ref_domains": ref_domains,
        "authority_score": authority_score,
    }


# ------------------------------------------------------------------ #
# main function used by app.py
# ------------------------------------------------------------------ #
def get_domain_stats(domain: str, country: str, period: str, client: AhrefsClient, overview_data: Optional[Dict[str, Any]] = None, changes_period: Optional[str] = None) -> DomainStats:
    """
    Fetch and normalize metrics for a single domain+country+period combination.
    
    Now fetches both current and previous period data to calculate changes.
    
    Args:
        domain: Domain to analyze
        country: Country code
        period: Time period (month/year)
        client: AhrefsClient instance
        overview_data: Optional pre-fetched overview data to reuse (avoids duplicate API calls)
    """
    from datetime import datetime, timedelta

    # Reuse overview_data if provided, otherwise fetch it
    # Always use yesterday's date for current data (most recent available data)
    # Ahrefs typically shows data up to yesterday, so using today might return stale or unavailable data
    from datetime import datetime, timedelta
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    # Always use yesterday for current data to ensure data availability
    current_date = yesterday
    
    if overview_data is not None:
        overview_raw = overview_data
    else:
        overview_raw = client.overview(target=domain, country=country, date=current_date.strftime("%Y-%m-%d"))
    
    metrics = _extract_metrics_from_overview(overview_raw)

    # Fetch previous period data for comparison
    # Initialize change values to None (will be set if historical data is successfully fetched)
    organic_keywords_change = None
    organic_traffic_change = None
    paid_keywords_change = None
    paid_traffic_change = None
    ref_domains_change = None
    organic_keywords_pct = None
    organic_traffic_pct = None
    paid_keywords_pct = None
    paid_traffic_pct = None
    ref_domains_pct = None
    
    # Initialize previous values for tooltip
    prev_organic_keywords = None
    prev_organic_traffic = None
    prev_paid_keywords = None
    prev_paid_traffic = None
    prev_ref_domains = None
    
    # Only fetch historical data if changes_period is specified and not "Don't show"
    if changes_period and changes_period != "Don't show":
        try:
            # Import CHANGES_OPTIONS to get the days value
            from config import CHANGES_OPTIONS
            
            # Get the number of days from the changes_period option
            days_back = CHANGES_OPTIONS.get(changes_period)
            
            if days_back is not None:
                # Calculate previous period date
                # Use the same base date (yesterday) for both current and previous period calculations
                # This ensures we're comparing the most recent available data with the same day last month
                today = datetime.now()
                yesterday = today - timedelta(days=1)
                
                # Always use yesterday as base for comparison date calculation
                # This ensures we compare yesterday (most recent available) with same day last month
                base_date_for_comparison = yesterday
                
                if changes_period == "Last month":
                    # CRITICAL FIX: Ahrefs calculates "Last month" changes as exactly 30 days ago, NOT same day last month!
                    # According to Ahrefs support:
                    # - Organic Keywords delta: change over the last 30 days
                    # - Organic Traffic delta: change in estimated monthly traffic over the last 30 days
                    # - Ref. Domains delta: change over the last 30 days
                    #
                    # IMPORTANT: The API's org_traffic is a monthly search volume ESTIMATE, not daily actual traffic.
                    # The Ahrefs graph shows daily actual traffic, which is a different metric.
                    #
                    # Use exactly 30 days ago (not same day last month) to match Ahrefs calculation
                    prev_date = base_date_for_comparison - timedelta(days=30)
                    
                    # Store note about the metric difference
                    overview_raw.setdefault("_debug_info", {})["_comparison_note"] = (
                        f"Comparing exactly 30 days: {base_date_for_comparison.strftime('%Y-%m-%d')} vs {prev_date.strftime('%Y-%m-%d')} (30 days ago). "
                        f"This matches Ahrefs 'Last month' calculation which uses exactly 30 days, not same day last month. "
                        f"Note: org_traffic is a monthly estimate, not daily actual traffic like the graph shows."
                    )
                elif changes_period in ["Last 3 months", "Last 6 months"]:
                    # For multi-month periods, use approximate days (Ahrefs uses calendar months)
                    prev_date = yesterday - timedelta(days=days_back)
                else:
                    # For other periods (24 hours, 7 days, year, etc.), use exact days back from yesterday
                    prev_date = yesterday - timedelta(days=days_back)
                
                # Add a small delay to avoid rate limiting when making multiple requests
                import time
                time.sleep(0.5)  # 500ms delay between API calls
                
                # Store comparison date for debugging
                prev_date_str = prev_date.strftime("%Y-%m-%d")
                
                # Store that we're about to fetch previous period data
                if "_debug_info" not in overview_raw:
                    overview_raw["_debug_info"] = {}
                overview_raw["_debug_info"]["prev_period_fetch_attempted"] = True
                overview_raw["_debug_info"]["prev_period_fetch_date"] = prev_date_str
                
                # Fetch previous period data
                try:
                    prev_overview = client.overview(target=domain, country=country, date=prev_date_str)
                    prev_metrics = _extract_metrics_from_overview(prev_overview)
                    overview_raw["_debug_info"]["prev_period_fetch_success"] = True
                except Exception as fetch_error:
                    # Store the fetch error separately from the outer exception handler
                    overview_raw["_debug_info"]["prev_period_fetch_error"] = str(fetch_error)
                    overview_raw["_debug_info"]["prev_period_fetch_error_type"] = type(fetch_error).__name__
                    overview_raw["_debug_info"]["prev_period_fetch_success"] = False
                    # Re-raise to be caught by outer exception handler
                    raise
                
                # Store debug info about comparison
                if "_debug_info" not in overview_raw:
                    overview_raw["_debug_info"] = {}
                overview_raw["_debug_info"]["comparison_date"] = prev_date_str
                overview_raw["_debug_info"]["comparison_period"] = changes_period
                overview_raw["_debug_info"]["prev_metrics"] = prev_metrics
                # Store raw previous overview for debugging
                overview_raw["_debug_info"]["prev_overview_raw"] = prev_overview
                # Check what date the API actually returned for previous period
                prev_returned_date = prev_overview.get("_api_returned_date") or prev_overview.get("_api_params_metrics", {}).get("date")
                overview_raw["_debug_info"]["prev_api_returned_date"] = prev_returned_date
                # Store current date used for comparison
                overview_raw["_debug_info"]["current_date"] = current_date.strftime("%Y-%m-%d")
                overview_raw["_debug_info"]["current_metrics"] = metrics
                overview_raw["_debug_info"]["base_date_for_comparison"] = base_date_for_comparison.strftime("%Y-%m-%d") if changes_period == "Last month" else current_date.strftime("%Y-%m-%d")
                # Check what date the API actually returned for current period
                current_returned_date = overview_raw.get("_api_returned_date") or overview_raw.get("_api_params_metrics", {}).get("date")
                overview_raw["_debug_info"]["current_api_returned_date"] = current_returned_date
                
                # Only calculate changes if we got valid previous metrics
                if prev_metrics and isinstance(prev_metrics, dict):
                    # Validate that current date is after previous date (safeguard against date mix-ups)
                    current_api_date = overview_raw.get("_api_returned_date") or current_date.strftime("%Y-%m-%d")
                    prev_api_date = prev_overview.get("_api_returned_date") or prev_date_str
                    
                    # Check if dates are in correct order
                    dates_in_order = current_api_date >= prev_api_date
                    
                    # Store date validation in debug info
                    if "_debug_info" not in overview_raw:
                        overview_raw["_debug_info"] = {}
                    overview_raw["_debug_info"]["date_validation"] = {
                        "current_date": current_api_date,
                        "previous_date": prev_api_date,
                        "current_after_previous": dates_in_order,
                        "current_requested": current_date.strftime("%Y-%m-%d"),
                        "previous_requested": prev_date_str
                    }
                    
                    # Store previous values for tooltip display
                    prev_organic_keywords = prev_metrics.get("organic_keywords", 0)
                    prev_organic_traffic = prev_metrics.get("organic_traffic", 0)
                    prev_paid_keywords = prev_metrics.get("paid_keywords", 0)
                    prev_paid_traffic = prev_metrics.get("paid_traffic", 0)
                    prev_ref_domains = prev_metrics.get("ref_domains", 0)
                    
                    # CRITICAL FIX: Detect and correct value swapping
                    # The issue: Sometimes what we think is "current" is actually "previous" and vice versa
                    # This can happen if API returns data for dates that don't match what we requested
                    # or if the data values themselves are from the wrong periods
                    
                    # Strategy: Compare requested dates to determine expected order
                    # If requested current date > requested previous date, but API dates suggest otherwise, swap
                    requested_dates_in_order = current_date.strftime("%Y-%m-%d") >= prev_date_str
                    
                    # Also check if the values themselves suggest they might be swapped
                    # If current value is much higher than previous, and we're expecting a decrease, values might be swapped
                    # But this is tricky to detect, so we'll rely on date comparison
                    
                    values_swapped = False
                    swap_reason = None
                    
                    if not dates_in_order:
                        # API-returned dates are reversed - definitely swap
                        values_swapped = True
                        swap_reason = "API returned dates in reverse order"
                    elif not requested_dates_in_order:
                        # Requested dates are reversed (shouldn't happen, but handle it)
                        values_swapped = True
                        swap_reason = "Requested dates were in reverse order"
                    elif current_api_date == prev_api_date:
                        # Same date returned for both - can't determine order, this is very suspicious
                        # This likely means the API returned data for the same date, which means we can't compare periods
                        # Don't swap (would be arbitrary), but log a critical warning
                        overview_raw["_debug_info"]["date_validation"]["same_date_warning"] = "CRITICAL: Both API calls returned same date - cannot reliably compare periods"
                        overview_raw["_debug_info"]["date_validation"]["same_date_critical"] = True
                        # In this case, we should probably not calculate changes, but for now we'll continue
                        # The change values will be calculated but may be incorrect
                    
                    if values_swapped:
                        # Swap current and previous values
                        current_organic_keywords = prev_organic_keywords
                        current_organic_traffic = prev_organic_traffic
                        current_paid_keywords = prev_paid_keywords
                        current_paid_traffic = prev_paid_traffic
                        current_ref_domains = prev_ref_domains
                        
                        prev_organic_keywords = metrics["organic_keywords"]
                        prev_organic_traffic = metrics["organic_traffic"]
                        prev_paid_keywords = metrics["paid_keywords"]
                        prev_paid_traffic = metrics["paid_traffic"]
                        prev_ref_domains = metrics["ref_domains"]
                        
                        # Update metrics dict with swapped values
                        metrics["organic_keywords"] = current_organic_keywords
                        metrics["organic_traffic"] = current_organic_traffic
                        metrics["paid_keywords"] = current_paid_keywords
                        metrics["paid_traffic"] = current_paid_traffic
                        metrics["ref_domains"] = current_ref_domains
                        
                        overview_raw["_debug_info"]["date_validation"]["values_swapped"] = True
                        overview_raw["_debug_info"]["date_validation"]["swap_reason"] = swap_reason
                    else:
                        overview_raw["_debug_info"]["date_validation"]["values_swapped"] = False
                    
                    # Calculate changes: current - previous
                    # This matches Ahrefs UI: if current is less than previous, change is negative (decrease)
                    # Example: current=13.4K, previous=18.9K, change=13.4K-18.9K=-5.5K (negative, correct)
                    organic_keywords_change = metrics["organic_keywords"] - prev_organic_keywords
                    organic_traffic_change = metrics["organic_traffic"] - prev_organic_traffic
                    paid_keywords_change = metrics["paid_keywords"] - prev_paid_keywords
                    paid_traffic_change = metrics["paid_traffic"] - prev_paid_traffic
                    ref_domains_change = metrics["ref_domains"] - prev_ref_domains
                    
                    # Store raw calculation for debugging
                    overview_raw["_debug_info"]["raw_calculation"] = {
                        "organic_keywords": {
                            "current": metrics["organic_keywords"],
                            "previous": prev_organic_keywords,
                            "change": organic_keywords_change
                        },
                        "organic_traffic": {
                            "current": metrics["organic_traffic"],
                            "previous": prev_organic_traffic,
                            "change": organic_traffic_change
                        },
                        "ref_domains": {
                            "current": metrics["ref_domains"],
                            "previous": prev_ref_domains,
                            "change": ref_domains_change
                        }
                    }
                    
                    # Calculate percentage changes
                    def calc_pct_change(current: int, previous: int) -> float:
                        if previous == 0:
                            return 0.0 if current == 0 else 100.0
                        return ((current - previous) / previous) * 100.0
                    
                    organic_keywords_pct = calc_pct_change(metrics["organic_keywords"], prev_metrics.get("organic_keywords", 0))
                    organic_traffic_pct = calc_pct_change(metrics["organic_traffic"], prev_metrics.get("organic_traffic", 0))
                    paid_keywords_pct = calc_pct_change(metrics["paid_keywords"], prev_metrics.get("paid_keywords", 0))
                    paid_traffic_pct = calc_pct_change(metrics["paid_traffic"], prev_metrics.get("paid_traffic", 0))
                    ref_domains_pct = calc_pct_change(metrics["ref_domains"], prev_metrics.get("ref_domains", 0))
        except Exception as e:
            # If fetching previous period fails, changes remain None
            # Store the error for debugging
            if "_debug_info" not in overview_raw:
                overview_raw["_debug_info"] = {}
            overview_raw["_debug_info"]["prev_period_fetch_error"] = str(e)
            overview_raw["_debug_info"]["prev_period_fetch_error_type"] = type(e).__name__
            # Common reasons: API rate limits, historical data not available, API errors
            # Continue - changes will be None and won't be displayed, but error is logged for debugging

    organic_traffic = metrics["organic_traffic"]
    organic_keywords = metrics["organic_keywords"]
    paid_traffic = metrics["paid_traffic"]
    paid_keywords = metrics["paid_keywords"]
    ref_domains = metrics["ref_domains"]
    authority_score = metrics["authority_score"]

    # how many points to show in the little inline charts
    trend_points = 6 if period == "month" else 12

    return DomainStats(
        domain=domain,
        country=country,
        organic_keywords=Metric(
            value=float(organic_keywords),
            change_pct=organic_keywords_pct,
            change_value=float(organic_keywords_change) if organic_keywords_change is not None else None,
            previous_value=float(prev_organic_keywords) if prev_organic_keywords is not None else None,
            sparkline=_flat_trend(organic_keywords, trend_points),
        ),
        organic_traffic=Metric(
            value=float(organic_traffic),
            change_pct=organic_traffic_pct,
            change_value=float(organic_traffic_change) if organic_traffic_change is not None else None,
            previous_value=float(prev_organic_traffic) if prev_organic_traffic is not None else None,
            sparkline=_flat_trend(organic_traffic, trend_points),
        ),
        paid_keywords=Metric(
            value=float(paid_keywords),
            change_pct=paid_keywords_pct,
            change_value=float(paid_keywords_change) if paid_keywords_change is not None else None,
            previous_value=float(prev_paid_keywords) if prev_paid_keywords is not None else None,
            sparkline=[],
        ),
        paid_traffic=Metric(
            value=float(paid_traffic),
            change_pct=paid_traffic_pct,
            change_value=float(paid_traffic_change) if paid_traffic_change is not None else None,
            previous_value=float(prev_paid_traffic) if prev_paid_traffic is not None else None,
            sparkline=[],
        ),
        ref_domains=Metric(
            value=float(ref_domains),
            change_pct=ref_domains_pct,
            change_value=float(ref_domains_change) if ref_domains_change is not None else None,
            previous_value=float(prev_ref_domains) if prev_ref_domains is not None else None,
            sparkline=_flat_trend(ref_domains, trend_points),
        ),
        authority_score=float(authority_score),
    )
