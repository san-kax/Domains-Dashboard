# stats_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ahrefs_client import AhrefsClient


# ------------------------------------------------------------------ #
# data structure consumed by the Streamlit UI
# ------------------------------------------------------------------ #
@dataclass
class DomainStats:
    domain: str
    country: str
    period: str  # "month" or "year"

    organic_keywords: int
    organic_keywords_change: float

    organic_traffic: int
    organic_traffic_change: float

    paid_keywords: int
    paid_keywords_change: float

    paid_traffic: int
    paid_traffic_change: float

    ref_domains: int
    ref_domains_change: float

    authority_score: int
    authority_change: float

    # tiny arrays used for the little sparkline charts
    organic_keywords_trend: list[int]
    organic_traffic_trend: list[int]
    ref_domains_trend: list[int]


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


def _flat_trend(value: int, points: int) -> list[int]:
    """Just repeat the current value N times to draw a flat sparkline."""
    return [value] * max(points, 1)


def _extract_metrics_from_overview(payload: Dict[str, Any]) -> Dict[str, int]:
    """
    Ahrefs v3 'overview' response shape can change / differ by plan.
    We'll be conservative and try a few common key patterns.

    After you run this once with your key, you can temporarily print
    the raw payload in Streamlit to see the exact structure and then
    tighten these mappings.
    """
    # Sometimes metrics are nested; sometimes top-level.
    metrics: Dict[str, Any] = payload.get("metrics") or payload

    organic_traffic = _safe_int(
        metrics.get("organic_traffic", metrics.get("organicTraffic"))
    )
    organic_keywords = _safe_int(
        metrics.get("organic_keywords", metrics.get("organicKeywords"))
    )
    paid_traffic = _safe_int(
        metrics.get("paid_traffic", metrics.get("paidTraffic"))
    )
    paid_keywords = _safe_int(
        metrics.get("paid_keywords", metrics.get("paidKeywords"))
    )

    ref_domains = _safe_int(
        metrics.get("ref_domains")
        or metrics.get("referring_domains")
        or metrics.get("referringDomains")
    )

    authority_score = _safe_int(
        metrics.get("domain_rating", metrics.get("domainRating"))
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
        period=period,
        organic_keywords=organic_keywords,
        organic_keywords_change=0.0,
        organic_traffic=organic_traffic,
        organic_traffic_change=0.0,
        paid_keywords=paid_keywords,
        paid_keywords_change=0.0,
        paid_traffic=paid_traffic,
        paid_traffic_change=0.0,
        ref_domains=ref_domains,
        ref_domains_change=0.0,
        authority_score=authority_score,
        authority_change=0.0,
        organic_keywords_trend=_flat_trend(organic_keywords, trend_points),
        organic_traffic_trend=_flat_trend(organic_traffic, trend_points),
        ref_domains_trend=_flat_trend(ref_domains, trend_points),
    )
