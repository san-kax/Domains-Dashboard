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
    change_pct: Optional[float]
    change_value: Optional[float]  # Actual numeric change (e.g., -667, +309)
    sparkline: List[float]


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
def get_domain_stats(domain: str, country: str, period: str, client: AhrefsClient, overview_data: Optional[Dict[str, Any]] = None) -> DomainStats:
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
    if overview_data is not None:
        overview_raw = overview_data
    else:
        overview_raw = client.overview(target=domain, country=country)
    
    metrics = _extract_metrics_from_overview(overview_raw)

    # Fetch previous period data for comparison
    try:
        # Calculate previous period date
        today = datetime.now()
        if period == "month":
            # Get data from one month ago (approximately 30 days)
            # For more accuracy, we could use dateutil.relativedelta, but this works for most cases
            prev_date = today - timedelta(days=30)
        else:  # year
            # Get data from one year ago
            prev_date = today - timedelta(days=365)
        
        # Fetch previous period data
        prev_overview = client.overview(target=domain, country=country, date=prev_date.strftime("%Y-%m-%d"))
        prev_metrics = _extract_metrics_from_overview(prev_overview)
        
        # Calculate changes
        organic_keywords_change = metrics["organic_keywords"] - prev_metrics["organic_keywords"]
        organic_traffic_change = metrics["organic_traffic"] - prev_metrics["organic_traffic"]
        paid_keywords_change = metrics["paid_keywords"] - prev_metrics["paid_keywords"]
        paid_traffic_change = metrics["paid_traffic"] - prev_metrics["paid_traffic"]
        ref_domains_change = metrics["ref_domains"] - prev_metrics["ref_domains"]
        
        # Calculate percentage changes
        def calc_pct_change(current: int, previous: int) -> float:
            if previous == 0:
                return 0.0 if current == 0 else 100.0
            return ((current - previous) / previous) * 100.0
        
        organic_keywords_pct = calc_pct_change(metrics["organic_keywords"], prev_metrics["organic_keywords"])
        organic_traffic_pct = calc_pct_change(metrics["organic_traffic"], prev_metrics["organic_traffic"])
        paid_keywords_pct = calc_pct_change(metrics["paid_keywords"], prev_metrics["paid_keywords"])
        paid_traffic_pct = calc_pct_change(metrics["paid_traffic"], prev_metrics["paid_traffic"])
        ref_domains_pct = calc_pct_change(metrics["ref_domains"], prev_metrics["ref_domains"])
    except Exception:
        # If fetching previous period fails, set changes to None
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
            sparkline=_flat_trend(organic_keywords, trend_points),
        ),
        organic_traffic=Metric(
            value=float(organic_traffic),
            change_pct=organic_traffic_pct,
            change_value=float(organic_traffic_change) if organic_traffic_change is not None else None,
            sparkline=_flat_trend(organic_traffic, trend_points),
        ),
        paid_keywords=Metric(
            value=float(paid_keywords),
            change_pct=paid_keywords_pct,
            change_value=float(paid_keywords_change) if paid_keywords_change is not None else None,
            sparkline=[],
        ),
        paid_traffic=Metric(
            value=float(paid_traffic),
            change_pct=paid_traffic_pct,
            change_value=float(paid_traffic_change) if paid_traffic_change is not None else None,
            sparkline=[],
        ),
        ref_domains=Metric(
            value=float(ref_domains),
            change_pct=ref_domains_pct,
            change_value=float(ref_domains_change) if ref_domains_change is not None else None,
            sparkline=_flat_trend(ref_domains, trend_points),
        ),
        authority_score=float(authority_score),
    )
