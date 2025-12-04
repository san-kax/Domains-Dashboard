# app.py

import os
from typing import Optional
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from config import MONITORED_DOMAINS, PERIOD_OPTIONS, CHANGES_OPTIONS, CHANGES_OPTIONS_LIST
from mock_data import mock_domain_stats
from ahrefs_client import AhrefsClient
from stats_service import get_domain_stats

load_dotenv()

st.set_page_config(page_title="Ahrefs Monitoring Dashboard", layout="wide")

# Check for API token in Streamlit secrets (after Streamlit is initialized)
# Check both naming conventions: AHREFS_API_TOKEN and A_HREFS_API_TOKEN
def get_ahrefs_token():
    """Get Ahrefs API token from Streamlit secrets or environment variables."""
    token = ""
    
    # Try Streamlit secrets first (for Streamlit Cloud)
    if hasattr(st, "secrets"):
        try:
            # Try both naming conventions - check if key exists
            if "AHREFS_API_TOKEN" in st.secrets:
                token = str(st.secrets["AHREFS_API_TOKEN"]).strip()
            elif "A_HREFS_API_TOKEN" in st.secrets:
                token = str(st.secrets["A_HREFS_API_TOKEN"]).strip()
        except (AttributeError, KeyError, TypeError, Exception) as e:
            # Secrets not available or key doesn't exist
            pass
    
    # If no token from secrets, try environment variables
    if not token:
        token = os.getenv("AHREFS_API_TOKEN", "").strip() or os.getenv("A_HREFS_API_TOKEN", "").strip()
    
    return token

# Check both environment variables and Streamlit secrets (for Streamlit Cloud)
# Default to mock data if not explicitly set to false
USE_MOCK_DATA_STR = "true"  # Default
if hasattr(st, "secrets"):
    try:
        if "USE_MOCK_DATA" in st.secrets:
            USE_MOCK_DATA_STR = str(st.secrets["USE_MOCK_DATA"]).strip()
    except (AttributeError, KeyError, TypeError, Exception):
        pass

# If not found in secrets, check environment variables
if USE_MOCK_DATA_STR == "true":
    USE_MOCK_DATA_STR = os.getenv("USE_MOCK_DATA", "true")
# If explicitly set to false, use real data (if token available)
# Otherwise default to mock data
USE_MOCK_DATA = USE_MOCK_DATA_STR.lower() not in ("false", "0", "no")

# Get API token
AHREFS_TOKEN = get_ahrefs_token()

# If USE_MOCK_DATA is false but no token, show warning and use mock data
if not USE_MOCK_DATA and not AHREFS_TOKEN:
    st.warning("⚠️ USE_MOCK_DATA is set to false but no API token found. Using mock data.")
    USE_MOCK_DATA = True

st.title("Domains for monitoring")

# --- Controls row --- #
col_period, col_changes = st.columns([1, 1])
with col_period:
    period = st.radio("Period", PERIOD_OPTIONS, horizontal=True, index=0)
with col_changes:
    # Default to "Last month" (index 3)
    changes_index = CHANGES_OPTIONS_LIST.index("Last month") if "Last month" in CHANGES_OPTIONS_LIST else 0
    changes_period = st.selectbox("Changes", CHANGES_OPTIONS_LIST, index=changes_index)

if USE_MOCK_DATA:
    st.info(
        "ℹ️ Using MOCK data. "
        "Set USE_MOCK_DATA=false and configure A_HREFS_API_TOKEN in Streamlit secrets to use real Ahrefs data."
    )
else:
    if AHREFS_TOKEN:
        st.success("✅ Using real Ahrefs API data")
    else:
        st.warning("⚠️ USE_MOCK_DATA=false but no API token found. Check your Streamlit secrets.")


def format_change_value(change_value: Optional[float]) -> Optional[str]:
    """
    Format change value in Ahrefs style (e.g., -667, +309, -40K, +3.5K).
    Uses K notation for thousands.
    """
    if change_value is None:
        return None
    
    abs_change = abs(change_value)
    sign = "+" if change_value >= 0 else ""
    
    # Format with K notation for values >= 1000
    if abs_change >= 1000:
        # Round to 1 decimal place for K notation
        formatted = abs_change / 1000
        # If it's a whole number, show without decimal
        if formatted == int(formatted):
            return f"{sign}{int(formatted)}K"
        else:
            # Show 1 decimal place
            return f"{sign}{formatted:.1f}K"
    else:
        # For values < 1000, show as integer
        return f"{sign}{int(change_value)}"


def format_date_for_tooltip(days_back: int) -> tuple:
    """Format current and previous dates for tooltip display."""
    from datetime import datetime, timedelta
    
    today = datetime.now()
    prev_date = today - timedelta(days=days_back)
    
    current_str = today.strftime("%b %Y")
    previous_str = prev_date.strftime("%b %Y")
    
    return current_str, previous_str


def metric_block(title: str, metric, show_chart: bool = True, changes_period: str = "Last month"):
    """
    Render a metric (value + change in Ahrefs format + optional sparkline) in a small panel.
    Includes hover tooltip with detailed comparison.
    """
    from config import CHANGES_OPTIONS
    
    col1, col2 = st.columns([1, 1])

    with col1:
        # Display change value in Ahrefs style (e.g., -667, +309) instead of percentage
        # Use getattr to handle cases where change_value might not exist (backward compatibility)
        change_val = getattr(metric, 'change_value', None)
        previous_val = getattr(metric, 'previous_value', None)
        change_pct = getattr(metric, 'change_pct', None)
        delta = format_change_value(change_val)
        
        # Display metric
        st.metric(title, f"{metric.value:,.0f}", delta)
        
        # Create tooltip if we have comparison data
        if change_val is not None and previous_val is not None:
            # Get dates for tooltip
            days_back = CHANGES_OPTIONS.get(changes_period) if changes_period else None
            if days_back:
                current_date, previous_date = format_date_for_tooltip(days_back)
            else:
                current_date = datetime.now().strftime("%b %Y")
                previous_date = "N/A"
            
            # Format values for tooltip
            current_value_formatted = f"{metric.value:,.0f}"
            if metric.value >= 1000:
                current_value_formatted = f"{metric.value/1000:.1f}K".rstrip('0').rstrip('.')
            
            previous_value_formatted = f"{previous_val:,.0f}"
            if previous_val >= 1000:
                previous_value_formatted = f"{previous_val/1000:.1f}K".rstrip('0').rstrip('.')
            
            diff_formatted = format_change_value(change_val)
            pct_formatted = f"{change_pct:+.2f}%" if change_pct is not None else "N/A"
            
            # Create tooltip using HTML/CSS that will attach to the delta via JavaScript
            tooltip_content = f"""
            <div style="padding: 10px; line-height: 1.8; font-size: 13px;">
                <div><strong>Current ({current_date}):</strong> {current_value_formatted}</div>
                <div><strong>Previous ({previous_date}):</strong> {previous_value_formatted}</div>
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #e0e0e0;">
                    <strong>Difference:</strong> {diff_formatted} ({pct_formatted})
                </div>
            </div>
            """
            
            # Inject CSS and JavaScript for tooltip
            import hashlib
            import json
            tooltip_id = hashlib.md5(f'{title}_{metric.value}_{delta}'.encode()).hexdigest()[:8]
            
            # Escape tooltip_content for JavaScript (replace backticks and escape quotes)
            escaped_tooltip = tooltip_content.replace('`', '\\`').replace('\\', '\\\\')
            
            st.markdown(f"""
            <style>
                .metric-tooltip-{tooltip_id} {{
                    position: absolute;
                    background-color: white;
                    color: #333;
                    padding: 0;
                    border-radius: 6px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    border: 1px solid #ddd;
                    min-width: 220px;
                    z-index: 1000;
                    display: none;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                }}
                .metric-tooltip-{tooltip_id}::after {{
                    content: "";
                    position: absolute;
                    top: 100%;
                    left: 50%;
                    margin-left: -5px;
                    border-width: 5px;
                    border-style: solid;
                    border-color: white transparent transparent transparent;
                }}
            </style>
            <script>
            (function() {{
                setTimeout(function() {{
                    // Find all metric containers
                    const containers = document.querySelectorAll('[data-testid="stMetric"]');
                    containers.forEach(function(container) {{
                        // Find delta element (usually a div with the delta value)
                        const deltaElements = container.querySelectorAll('div');
                        deltaElements.forEach(function(el) {{
                            if (el.textContent && el.textContent.trim() === '{delta}') {{
                                // Create tooltip element
                                const tooltip = document.createElement('div');
                                tooltip.className = 'metric-tooltip-{tooltip_id}';
                                tooltip.innerHTML = `{escaped_tooltip}`;
                                document.body.appendChild(tooltip);
                                
                                // Add hover events
                                el.style.cursor = 'help';
                                el.addEventListener('mouseenter', function(e) {{
                                    tooltip.style.display = 'block';
                                    const rect = el.getBoundingClientRect();
                                    tooltip.style.left = (rect.left + rect.width / 2 - 110) + 'px';
                                    tooltip.style.top = (rect.top - tooltip.offsetHeight - 10) + 'px';
                                }});
                                el.addEventListener('mouseleave', function() {{
                                    tooltip.style.display = 'none';
                                }});
                            }}
                        }});
                    }});
                }}, 500);
            }})();
            </script>
            """, unsafe_allow_html=True)

    if show_chart and metric.sparkline:
        with col2:
            df = pd.DataFrame(metric.sparkline, columns=[title])
            st.line_chart(df, height=60)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stats(domain: str, country: str, period: str, changes_period: str = "Last month"):
    """
    Cached wrapper for either mock stats or real Ahrefs stats.
    """
    if USE_MOCK_DATA:
        return mock_domain_stats(domain, country, period)
    
    # Try to use real Ahrefs data, but fallback to mock if API key is missing or request fails
    try:
        # Use the token we got from secrets/env
        client = AhrefsClient(api_key=AHREFS_TOKEN) if AHREFS_TOKEN else AhrefsClient()
        
        # Get raw overview data for debugging
        overview_data = client.overview(target=domain, country=country)
        
        # Always show debug info when using real API (for now, to diagnose)
        with st.expander("🔍 Debug: Raw API Responses (click to view)", expanded=False):
            st.write("**Domain Rating Response:**")
            if overview_data.get("_raw_dr_response"):
                st.json(overview_data.get("_raw_dr_response"))
            else:
                st.write("No domain rating response stored")
            
            st.write("**Metrics Response:**")
            if overview_data.get("_raw_metrics_response"):
                st.json(overview_data.get("_raw_metrics_response"))
            else:
                st.write("No metrics response stored")
            
            st.write("**Backlinks Stats Response:**")
            if overview_data.get("_raw_backlinks_response"):
                st.json(overview_data.get("_raw_backlinks_response"))
            else:
                st.write("No backlinks stats response stored")
            
            st.write("**Extracted Data (from metrics endpoint):**")
            if overview_data.get("_extracted_data"):
                st.json(overview_data.get("_extracted_data"))
            else:
                st.write("No extracted data stored")
            
            st.write("**Final Extracted Metrics (used by dashboard):**")
            final_metrics = {k: v for k, v in overview_data.items() if not k.startswith("_")}
            st.json(final_metrics)
            
            # Show debug info for ref_domains extraction
            if overview_data.get("_extracted_ref_domains") is not None:
                st.write("**Referring Domains Extraction Debug:**")
                st.write(f"- Raw value found: {overview_data.get('_extracted_ref_domains')}")
                st.write(f"- Converted to int: {overview_data.get('_extracted_ref_domains_int')}")
                st.write(f"- Source: {overview_data.get('_extracted_ref_domains_source')}")
                st.write(f"- Final value in metrics: {final_metrics.get('ref_domains', 'NOT FOUND')}")
            
            if overview_data.get("_errors"):
                st.write("**Errors:**")
                st.write(overview_data.get("_errors"))
        
        # Reuse the overview_data we already fetched instead of calling the API again
        # This ensures we're using the same data that's shown in the debug section
        result = get_domain_stats(domain, country, period, client, overview_data=overview_data, changes_period=changes_period)
        
        # Check if all key metrics are 0 (only show warning if truly all are zero)
        all_zero = (
            hasattr(result, 'organic_keywords') and result.organic_keywords.value == 0 and
            hasattr(result, 'organic_traffic') and result.organic_traffic.value == 0 and
            hasattr(result, 'ref_domains') and result.ref_domains.value == 0
        )
        # Only show warning if all are zero AND authority score is also 0 (indicating no data at all)
        if all_zero and hasattr(result, 'authority_score') and result.authority_score == 0:
            st.warning("⚠️ All metrics are showing as 0. Please check the debug section above to see the raw API responses.")
        
        return result
    except RuntimeError as e:
        if "API key is not configured" in str(e):
            st.warning(
                f"⚠️ Ahrefs API key not configured. Using mock data for {domain}. "
                "Set AHREFS_API_TOKEN or A_HREFS_API_TOKEN in Streamlit secrets to use real data."
            )
            return mock_domain_stats(domain, country, period)
        raise
    except requests.HTTPError as e:
        # Handle HTTP errors from Ahrefs API
        error_msg = str(e)
        st.error(f"❌ Ahrefs API Error for {domain}: {error_msg}")
        
        # Show more details for 404 errors
        if hasattr(e, 'response') and e.response and e.response.status_code == 404:
            st.info("💡 Tip: Some Ahrefs API endpoints may not be available in your plan. The app will use available data and fall back to mock data for missing metrics.")
        
        st.info("🔄 Falling back to mock data. Please check your API token, permissions, and endpoint availability.")
        return mock_domain_stats(domain, country, period)
    except Exception as e:
        # Handle any other errors
        st.error(f"❌ Error fetching data for {domain}: {str(e)}")
        st.info("🔄 Falling back to mock data.")
        return mock_domain_stats(domain, country, period)


# --- Main loop: one "card" per domain+country --- #

for item in MONITORED_DOMAINS:
    domain = item["domain"]
    country = item["country"]
    label = item.get("label", f"{domain} {country}")
    flag = item.get("flag", "")

    stats = fetch_stats(domain, country, period, changes_period)

    # Visual separator between rows
    st.markdown("---")

    # Header row: domain label + Authority Score
    # Use equal column widths to ensure proper alignment
    header_cols = st.columns([3, 1])
    with header_cols[0]:
        # Display label with flag, but avoid duplication if flag is already in label
        display_label = label if flag in label else f"{label} {flag}"
        st.markdown(f"### {display_label}")
    with header_cols[1]:
        # Use consistent formatting for Authority Score to align with other metrics
        st.metric("Authority Score", f"{stats.authority_score:.0f}", delta=None)

    # Metrics row: Organic KW, Organic Traffic, Ref Domains
    c1, c2, c3 = st.columns([2, 2, 2])

    with c1:
        metric_block("Organic Keywords", stats.organic_keywords, changes_period=changes_period)

    with c2:
        metric_block("Organic Traffic", stats.organic_traffic, changes_period=changes_period)

    with c3:
        metric_block("Ref. Domains", stats.ref_domains, changes_period=changes_period)


st.markdown("---")
st.caption("Simple Ahrefs monitoring dashboard built with Streamlit.")
