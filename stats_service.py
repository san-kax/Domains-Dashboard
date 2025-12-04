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
    # For "Last month" comparison, use today's date to match Ahrefs (Dec 4 vs Nov 4)
    # For other comparisons, use yesterday's date (data availability)
    from datetime import datetime, timedelta
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    # Determine which date to use for current data
    # If comparing "Last month", use today to match Ahrefs graph (Dec 4 vs Nov 4)
    # Otherwise, use yesterday for data availability
    current_date = today if changes_period == "Last month" else yesterday
    
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
                # For "Last month" comparison, Ahrefs uses TODAY's date as base (not yesterday)
                # This matches the Ahrefs graph which shows Dec 4 vs Nov 4
                # But we fetch current data for yesterday (Dec 3) to match Ahrefs data availability
                today = datetime.now()
                yesterday = today - timedelta(days=1)
                
                # For "Last month", use today's date to calculate comparison date
                # This ensures we compare Dec 4 with Nov 4 (not Dec 3 with Nov 3)
                base_date_for_comparison = today if changes_period == "Last month" else yesterday
                
                if changes_period == "Last month":
                    # For "Last month", Ahrefs compares current date with the same day of the previous month
                    # Based on Ahrefs graph: Dec 4 vs Nov 4 (same day last month)
                    # Use today's date as base for comparison calculation
                    import calendar
                    if base_date_for_comparison.month == 1:
                        # If current month is January, previous month is December of last year
                        prev_month = 12
                        prev_year = base_date_for_comparison.year - 1
                        last_day_prev_month = calendar.monthrange(prev_year, prev_month)[1]
                        # Use same day, but ensure it doesn't exceed days in previous month
                        prev_day = min(base_date_for_comparison.day, last_day_prev_month)
                        prev_date = datetime(prev_year, prev_month, prev_day)
                    else:
                        # Use same day of previous month (based on today's date, not yesterday)
                        prev_month = base_date_for_comparison.month - 1
                        prev_year = base_date_for_comparison.year
                        last_day_prev_month = calendar.monthrange(prev_year, prev_month)[1]
                        # Use same day, but ensure it doesn't exceed days in previous month
                        prev_day = min(base_date_for_comparison.day, last_day_prev_month)
                        prev_date = datetime(prev_year, prev_month, prev_day)
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
                
                # Fetch previous period data
                prev_overview = client.overview(target=domain, country=country, date=prev_date_str)
                prev_metrics = _extract_metrics_from_overview(prev_overview)
                
                # Store debug info about comparison
                if "_debug_info" not in overview_raw:
                    overview_raw["_debug_info"] = {}
                overview_raw["_debug_info"]["comparison_date"] = prev_date_str
                overview_raw["_debug_info"]["comparison_period"] = changes_period
                overview_raw["_debug_info"]["prev_metrics"] = prev_metrics
                # Store raw previous overview for debugging
                overview_raw["_debug_info"]["prev_overview_raw"] = prev_overview
                # Store current date used for comparison
                overview_raw["_debug_info"]["current_date"] = current_date.strftime("%Y-%m-%d")
                overview_raw["_debug_info"]["current_metrics"] = metrics
                overview_raw["_debug_info"]["base_date_for_comparison"] = base_date_for_comparison.strftime("%Y-%m-%d") if changes_period == "Last month" else current_date.strftime("%Y-%m-%d")
                
                # Only calculate changes if we got valid previous metrics
                if prev_metrics and isinstance(prev_metrics, dict):
                    # Store previous values for tooltip display
                    prev_organic_keywords = prev_metrics.get("organic_keywords", 0)
                    prev_organic_traffic = prev_metrics.get("organic_traffic", 0)
                    prev_paid_keywords = prev_metrics.get("paid_keywords", 0)
                    prev_paid_traffic = prev_metrics.get("paid_traffic", 0)
                    prev_ref_domains = prev_metrics.get("ref_domains", 0)
                    
                    # Calculate changes (even if previous values are 0, that's still valid historical data)
                    organic_keywords_change = metrics["organic_keywords"] - prev_organic_keywords
                    organic_traffic_change = metrics["organic_traffic"] - prev_organic_traffic
                    paid_keywords_change = metrics["paid_keywords"] - prev_paid_keywords
                    paid_traffic_change = metrics["paid_traffic"] - prev_paid_traffic
                    ref_domains_change = metrics["ref_domains"] - prev_ref_domains
                    
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
            # This is expected if historical data is not available for the domain/date
            # Common reasons: API rate limits, historical data not available, API errors
            # Silently continue - changes will be None and won't be displayed
            pass

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
