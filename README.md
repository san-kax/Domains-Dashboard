# Ahrefs Monitoring Dashboard (Streamlit)

This is a simple Streamlit dashboard that mimics a "Domains for monitoring" table
similar to the one in Ahrefs.

It shows, for each `domain + country`:

- Organic Keywords (value + % change + sparkline)
- Organic Traffic (value + % change + sparkline)
- Paid Keywords
- Paid Traffic
- Referring Domains (value + % change + sparkline)
- Authority Score (DR)

## Features

- Python + Streamlit
- Optional integration with **Ahrefs API v3** (Enterprise plan)
- Mock data mode for easy testing without any API keys
- Ready to deploy on **Streamlit Cloud** and **GitHub**

---

## Quick start (local)

1. Clone or download this project.

2. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env
   ```

   By default, `USE_MOCK_DATA=true` so you can see the dashboard immediately
   with static mock data.

4. Run the app:

   ```bash
   streamlit run app.py
   ```

5. Open the URL Streamlit prints (usually `http://localhost:8501`).

---

## Using real Ahrefs data

1. Make sure your Ahrefs account has access to **API v3**.

2. Set environment variables (locally in `.env`, or in Streamlit Cloud):

   - `A_HREFS_API_TOKEN` – your Ahrefs v3 token
   - `USE_MOCK_DATA=false`

3. Check the following files and align fields with your real responses:

   - `ahrefs_client.py`
   - `stats_service.py`
     - `_extract_metric_from_positions`
     - `_extract_refdomains`
     - `get_domain_stats` (the `batch_domain_metrics` indexing)

To adjust, temporarily print one of the responses inside the code, inspect the JSON,
and remap the fields so:

- `total` matches the metric total value
- `history` array provides values for sparklines
- `domain_rating` (or equivalent) is used as Authority Score

---

## Deploying on Streamlit Cloud

1. Push this folder to a GitHub repo.

2. In Streamlit Cloud:
   - Click **New app** and point to your repo & `app.py`.
   - Set **Secrets**:
     - `A_HREFS_API_TOKEN: "your_real_token"`
   - Set **Environment variables**:
     - `USE_MOCK_DATA=false` (if you want live data)

3. Deploy. Streamlit will install from `requirements.txt`
   and run `app.py`.

---

## Customizing domains

Edit `config.py`:

```python
MONITORED_DOMAINS = [
    {"domain": "example.com", "country": "US", "label": "example.com US", "flag": "🇺🇸"},
    {"domain": "example.com", "country": "UK", "label": "example.com UK", "flag": "🇬🇧"},
]
```

Add as many rows as you want.
