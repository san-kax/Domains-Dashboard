# stats_service.py

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from ahrefs_client import AhrefsClient


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


def _period_dates(period: str):
    """
    For 'Month': last 30 days vs previous 30.
    For 'Year': last 365 days vs previous 365.
    """
    today = date.today()
    period = period.lower()
    days = 30 if period == "month" else 365

    current_from = today - timedelta(days=days)
    current_to = today

    prev_to = current_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=days - 1)

    return current_from, current_to, prev_from, prev_to


def _pct_change(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return (current - previous) / previous * 100.0


def _extract_metric_from_positions(resp: dict, metric_key: str) -> Metric:
    """
    Extract a Metric from the positions_overview response.

    You MUST adapt this to the exact shape of your v3 response.
    As a starting guess, we're assuming something like:

    {
      "metrics": {
        "organic_keywords": {
          "total": 6400,
          "history": [
             {"date": "2024-10-01", "value": 6500},
             ...
          ]
        },
        ...
      }
    }
    """
    metrics = resp.get("metrics", {})
    metric_info = metrics.get(metric_key, {})

    total = float(metric_info.get("total", 0.0))
    history = metric_info.get("history", [])
    sparkline = [float(point.get("value", 0.0)) for point in history]

    return Metric(value=total, change_pct=None, sparkline=sparkline)


def _extract_refdomains(resp: dict) -> Metric:
    """
    Extract referring domains metric from backlinks_overview response.

    Again, adapt to actual response. Assumed pattern:

    {
      "metrics": {
        "refdomains": {
          "total": 41000,
          "history": [
             {"date": "2024-10-01", "value": 39500},
             ...
          ]
        }
      }
    }
    """
    metrics = resp.get("metrics", {})
    metric_info = metrics.get("refdomains", {})

    total = float(metric_info.get("total", 0.0))
    history = metric_info.get("history", [])
    sparkline = [float(point.get("value", 0.0)) for point in history]

    return Metric(value=total, change_pct=None, sparkline=sparkline)


def get_domain_stats(domain: str, country: str, period: str, client: AhrefsClient) -> DomainStats:
    current_from, current_to, prev_from, prev_to = _period_dates(period)

    # -------- fetch current period -------- #
    pos_current = client.positions_overview(domain, country, current_from, current_to)
    back_current = client.backlinks_overview(domain, current_from, current_to)

    organic_keywords_curr = _extract_metric_from_positions(pos_current, "organic_keywords")
    organic_traffic_curr = _extract_metric_from_positions(pos_current, "organic_traffic")
    paid_keywords_curr = _extract_metric_from_positions(pos_current, "paid_keywords")
    paid_traffic_curr = _extract_metric_from_positions(pos_current, "paid_traffic")
    ref_domains_curr = _extract_refdomains(back_current)

    # -------- fetch previous period -------- #
    pos_prev = client.positions_overview(domain, country, prev_from, prev_to)
    back_prev = client.backlinks_overview(domain, prev_from, prev_to)

    organic_keywords_prev = _extract_metric_from_positions(pos_prev, "organic_keywords")
    organic_traffic_prev = _extract_metric_from_positions(pos_prev, "organic_traffic")
    paid_keywords_prev = _extract_metric_from_positions(pos_prev, "paid_keywords")
    paid_traffic_prev = _extract_metric_from_positions(pos_prev, "paid_traffic")
    ref_domains_prev = _extract_refdomains(back_prev)

    # -------- compute % changes -------- #
    organic_keywords_curr.change_pct = _pct_change(
        organic_keywords_curr.value, organic_keywords_prev.value
    )
    organic_traffic_curr.change_pct = _pct_change(
        organic_traffic_curr.value, organic_traffic_prev.value
    )
    paid_keywords_curr.change_pct = _pct_change(
        paid_keywords_curr.value, paid_keywords_prev.value
    )
    paid_traffic_curr.change_pct = _pct_change(
        paid_traffic_curr.value, paid_traffic_prev.value
    )
    ref_domains_curr.change_pct = _pct_change(ref_domains_curr.value, ref_domains_prev.value)

    # -------- authority score (DR) -------- #
    batch = client.batch_domain_metrics([domain])
    # Adjust this indexing to match your real batch-analysis response
    # Example assumption:
    # {
    #   "results": {
    #       "gambling.com": {"domain_rating": 52}
    #   }
    # }
    results = batch.get("results", {})
    dom_info = results.get(domain, {})
    dr = float(dom_info.get("domain_rating", 0.0))

    return DomainStats(
        domain=domain,
        country=country,
        organic_keywords=organic_keywords_curr,
        organic_traffic=organic_traffic_curr,
        paid_keywords=paid_keywords_curr,
        paid_traffic=paid_traffic_curr,
        ref_domains=ref_domains_curr,
        authority_score=dr,
    )
