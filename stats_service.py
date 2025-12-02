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
    if "metrics" in payload and isinstance(payload["metrics"], dict):
        # If nested structure exists, use it
        metrics: Dict[str, Any] = payload["metrics"]
    else:
        # Otherwise, payload is already flat with metrics at top level
        metrics = payload

    # Extract organic traffic - try multiple key variations
    # Use explicit None checks instead of 'or' to handle 0 as a valid value
    organic_traffic = None
    for key in ["organic_traffic", "organicTraffic", "org_traffic"]:
        if key in metrics and metrics[key] is not None:
            organic_traffic = metrics[key]
            break
    organic_traffic = _safe_int(organic_traffic) if organic_traffic is not None else 0
    
    # Extract organic keywords - try multiple key variations
    organic_keywords = None
    for key in ["organic_keywords", "organicKeywords", "org_keywords"]:
        if key in metrics and metrics[key] is not None:
            organic_keywords = metrics[key]
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

    For now we only call Site Explorer 'overview', and we **don't** try to
    compute previous-period deltas from the API (no time-range endpoint used).
    So all *_change values are 0.0 and sparkline charts are flat.
    
    Args:
        domain: Domain to analyze
        country: Country code
        period: Time period (month/year)
        client: AhrefsClient instance
        overview_data: Optional pre-fetched overview data to reuse (avoids duplicate API calls)
    """

    # Reuse overview_data if provided, otherwise fetch it
    if overview_data is not None:
        overview_raw = overview_data
    else:
        overview_raw = client.overview(target=domain, country=country)
    
    metrics = _extract_metrics_from_overview(overview_raw)

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
            change_pct=0.0,  # No historical data available yet
            sparkline=_flat_trend(organic_keywords, trend_points),
        ),
        organic_traffic=Metric(
            value=float(organic_traffic),
            change_pct=0.0,  # No historical data available yet
            sparkline=_flat_trend(organic_traffic, trend_points),
        ),
        paid_keywords=Metric(
            value=float(paid_keywords),
            change_pct=0.0,  # No historical data available yet
            sparkline=[],
        ),
        paid_traffic=Metric(
            value=float(paid_traffic),
            change_pct=0.0,  # No historical data available yet
            sparkline=[],
        ),
        ref_domains=Metric(
            value=float(ref_domains),
            change_pct=0.0,  # No historical data available yet
            sparkline=_flat_trend(ref_domains, trend_points),
        ),
        authority_score=float(authority_score),
    )
