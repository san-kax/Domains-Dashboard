# app.py

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import MONITORED_DOMAINS, PERIOD_OPTIONS
from mock_data import mock_domain_stats
from ahrefs_client import AhrefsClient
from stats_service import get_domain_stats

load_dotenv()

USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

st.set_page_config(page_title="Ahrefs Monitoring Dashboard", layout="wide")

st.title("Domains for monitoring")

# --- Controls row --- #
period = st.radio("Period", PERIOD_OPTIONS, horizontal=True, index=0)

if USE_MOCK_DATA:
    st.info(
        "Using MOCK data (USE_MOCK_DATA=true). "
        "Set USE_MOCK_DATA=false and configure A_HREFS_API_TOKEN to pull real Ahrefs data."
    )


def metric_block(title: str, metric, show_chart: bool = True):
    """
    Render a metric (value + % change + optional sparkline) in a small panel.
    """
    col1, col2 = st.columns([1, 1])

    with col1:
        delta = None
        if metric.change_pct is not None:
            delta = f"{metric.change_pct:+.2f}%"
        st.metric(title, f"{metric.value:,.0f}", delta)

    if show_chart and metric.sparkline:
        with col2:
            df = pd.DataFrame(metric.sparkline, columns=[title])
            st.line_chart(df, height=60)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stats(domain: str, country: str, period: str):
    """
    Cached wrapper for either mock stats or real Ahrefs stats.
    """
    if USE_MOCK_DATA:
        return mock_domain_stats(domain, country, period)
    client = AhrefsClient()
    return get_domain_stats(domain, country, period, client)


# --- Main loop: one "card" per domain+country --- #

for item in MONITORED_DOMAINS:
    domain = item["domain"]
    country = item["country"]
    label = item.get("label", f"{domain} {country}")
    flag = item.get("flag", "")

    stats = fetch_stats(domain, country, period)

    # Visual separator between rows
    st.markdown("---")

    # Header row: domain label + Authority Score
    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.markdown(f"### {label} {flag}")
    with header_cols[1]:
        st.metric("Authority Score", f"{stats.authority_score:.0f}")

    # Metrics row: Organic KW, Organic Traffic, Paid KW, Paid Traffic, Ref Domains
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])

    with c1:
        metric_block("Organic Keywords", stats.organic_keywords)

    with c2:
        metric_block("Organic Traffic", stats.organic_traffic)

    with c3:
        metric_block("Paid Keywords", stats.paid_keywords, show_chart=False)

    with c4:
        metric_block("Paid Traffic", stats.paid_traffic, show_chart=False)

    with c5:
        metric_block("Ref. Domains", stats.ref_domains)


st.markdown("---")
st.caption("Simple Ahrefs monitoring dashboard built with Streamlit.")
