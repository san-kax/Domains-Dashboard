# mock_data.py

from stats_service import DomainStats, Metric


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
                change_value=-230,  # Example: decreased by 230 keywords
                previous_value=6630,  # Previous value for tooltip
                sparkline=[6500, 6480, 6460, 6450, 6420, 6410, 6400],
            ),
            organic_traffic=Metric(
                value=3200,
                change_pct=19.79,
                change_value=530,  # Example: increased by 530 traffic
                previous_value=2670,  # Previous value for tooltip
                sparkline=[2600, 2700, 2800, 2950, 3100, 3150, 3200],
            ),
            paid_keywords=Metric(
                value=0,
                change_pct=0.0,
                change_value=0.0,
                sparkline=[],
            ),
            paid_traffic=Metric(
                value=0,
                change_pct=0.0,
                change_value=0.0,
                sparkline=[],
            ),
            ref_domains=Metric(
                value=41000,
                change_pct=5.65,
                change_value=2317,  # Example: increased by 2317 referring domains
                previous_value=38683,  # Previous value for tooltip
                sparkline=[38800, 39200, 39900, 40500, 40800, 41000, 41050],
            ),
            authority_score=52,
        )

    # Default mock for other domains - using realistic change values based on Ahrefs screenshot
    # For www.gambling.com/uk: -667 keywords, -40K traffic, +309 ref domains
    if "uk" in domain.lower() or country == "GB":
        return DomainStats(
            domain=domain,
            country=country,
            organic_keywords=Metric(
                value=7726,
                change_pct=-7.95,  # Approximate percentage for -667 from ~8400
                change_value=-667,
                previous_value=8393,  # Previous value for tooltip
                sparkline=[8400, 8300, 8100, 8000, 7800, 7750, 7726],
            ),
            organic_traffic=Metric(
                value=82296,
                change_pct=-32.7,  # Approximate percentage for -40K from ~122K
                change_value=-40000,
                previous_value=122296,  # Previous value for tooltip
                sparkline=[122000, 115000, 105000, 95000, 88000, 85000, 82296],
            ),
            paid_keywords=Metric(
                value=2,
                change_pct=0.0,
                change_value=2,
                sparkline=[],
            ),
            paid_traffic=Metric(
                value=2,
                change_pct=0.0,
                change_value=2,
                sparkline=[],
            ),
            ref_domains=Metric(
                value=14022,
                change_pct=2.25,  # Approximate percentage for +309 from ~13713
                change_value=309,
                previous_value=13713,  # Previous value for tooltip
                sparkline=[13713, 13750, 13800, 13850, 13900, 13950, 14022],
            ),
            authority_score=78,
        )
    
    # Default mock for other domains
    return DomainStats(
        domain=domain,
        country=country,
        organic_keywords=Metric(
            value=2600,
            change_pct=-0.19,
            change_value=-5,
            previous_value=2605,  # Previous value for tooltip
            sparkline=[2700, 2680, 2660, 2650, 2630, 2610, 2600],
        ),
        organic_traffic=Metric(
            value=33000,
            change_pct=15.16,
            change_value=4344,
            previous_value=28656,  # Previous value for tooltip
            sparkline=[28500, 29000, 30000, 31500, 32000, 32500, 33000],
        ),
        paid_keywords=Metric(
            value=0,
            change_pct=0.0,
            change_value=0.0,
            sparkline=[],
        ),
        paid_traffic=Metric(
            value=0,
            change_pct=0.0,
            change_value=0.0,
            sparkline=[],
        ),
        ref_domains=Metric(
            value=41000,
            change_pct=5.65,
            change_value=2317,
            previous_value=38683,  # Previous value for tooltip
            sparkline=[39500, 39800, 40000, 40200, 40500, 40800, 41000],
        ),
        authority_score=52,
    )
