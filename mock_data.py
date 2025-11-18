# mock_data.py

from dataclasses import dataclass
from typing import List, Optional


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


def mock_domain_stats(domain: str, country: str, period: str) -> DomainStats:
    """
    Return static but realistic-looking data so the dashboard
    renders even without Ahrefs API access.
    """
    if domain == "gambling.com" and country == "AU":
        return DomainStats(
            domain=domain,
            country=country,
            organic_keywords=Metric(
                value=6400,
                change_pct=-3.58,
                sparkline=[6500, 6480, 6460, 6450, 6420, 6410, 6400],
            ),
            organic_traffic=Metric(
                value=3200,
                change_pct=19.79,
                sparkline=[2600, 2700, 2800, 2950, 3100, 3150, 3200],
            ),
            paid_keywords=Metric(
                value=0,
                change_pct=0.0,
                sparkline=[],
            ),
            paid_traffic=Metric(
                value=0,
                change_pct=0.0,
                sparkline=[],
            ),
            ref_domains=Metric(
                value=41000,
                change_pct=5.65,
                sparkline=[38800, 39200, 39900, 40500, 40800, 41000, 41050],
            ),
            authority_score=52,
        )

    # Default mock for other domains
    return DomainStats(
        domain=domain,
        country=country,
        organic_keywords=Metric(
            value=2600,
            change_pct=-0.19,
            sparkline=[2700, 2680, 2660, 2650, 2630, 2610, 2600],
        ),
        organic_traffic=Metric(
            value=33000,
            change_pct=15.16,
            sparkline=[28500, 29000, 30000, 31500, 32000, 32500, 33000],
        ),
        paid_keywords=Metric(
            value=0,
            change_pct=0.0,
            sparkline=[],
        ),
        paid_traffic=Metric(
            value=0,
            change_pct=0.0,
            sparkline=[],
        ),
        ref_domains=Metric(
            value=41000,
            change_pct=5.65,
            sparkline=[39500, 39800, 40000, 40200, 40500, 40800, 41000],
        ),
        authority_score=52,
    )
