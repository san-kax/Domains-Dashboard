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
    
    The overview() method now returns metrics directly as a dictionary,
    so we can use them as-is.
    """
    # The payload is already a metrics dictionary from overview()
    # Handle both nested and flat structures
    metrics: Dict[str, Any] = payload.get("metrics") or payload

    organic_traffic = _safe_int(
        metrics.get("organic_traffic") or metrics.get("organicTraffic") or 0
    )
    organic_keywords = _safe_int(
        metrics.get("organic_keywords") or metrics.get("organicKeywords") or 0
    )
    paid_traffic = _safe_int(
        metrics.get("paid_traffic") or metrics.get("paidTraffic") or 0
    )
    paid_keywords = _safe_int(
        metrics.get("paid_keywords") or metrics.get("paidKeywords") or 0
    )

    ref_domains = _safe_int(
        metrics.get("ref_domains")
        or metrics.get("referring_domains")
        or metrics.get("referringDomains")
        or metrics.get("refdomains")
        or 0
    )

    authority_score = _safe_int(
        metrics.get("domain_rating")
        or metrics.get("domainRating")
        or metrics.get("dr")
        or 0
    )

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
def get_domain_stats(domain: str, country: str, period: str, client: AhrefsClient) -> DomainStats:
    """
    Fetch and normalize metrics for a single domain+country+period combination.

    For now we only call Site Explorer 'overview', and we **don't** try to
    compute previous-period deltas from the API (no time-range endpoint used).
    So all *_change values are 0.0 and sparkline charts are flat.
    """

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
