"""
Sigma Intelligence Platform — Command Center Dashboard
Day 12 | 7-Agent Self-Healing Pipeline on AWS Bedrock

Streamlit secrets structure (add to .streamlit/secrets.toml):

[aws]
region          = "us-east-1"
access_key_id   = "..."
secret_access_key = "..."
s3_bucket       = "sigma-datatech-<your-team>"

[snowflake]
account         = "..."
user            = "..."
password        = "..."
database        = "SIGMA"
schema          = "SILVER"
warehouse       = "SIGMA_WH"

[agents]
supervisor_id   = "..."
knowledge_base_id = "..."
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from io import StringIO

import boto3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sigma Intelligence Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# GLOBAL CSS — TERMINAL WAR-ROOM THEME
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Sora:wght@300;400;600;700;800&display=swap');

/* ── Root ── */
:root {
    --bg0:      #020811;
    --bg1:      #080f1e;
    --bg2:      #0d1829;
    --bg3:      #132035;
    --border:   #1e3050;
    --primary:  #00e5ff;
    --success:  #00ff88;
    --warn:     #ffaa00;
    --danger:   #ff3c5a;
    --muted:    #4a6080;
    --text:     #c8daf0;
    --textdim:  #6b85a0;
    --mono:     'JetBrains Mono', monospace;
    --sans:     'Sora', sans-serif;
}

/* ── Global ── */
html, body, [class*="css"] {
    font-family: var(--sans) !important;
    background-color: var(--bg0) !important;
    color: var(--text) !important;
}

/* ── Streamlit wrappers ── */
.main .block-container {
    padding: 1.5rem 2rem 3rem !important;
    max-width: 1600px;
}
section[data-testid="stSidebar"] {
    background-color: var(--bg1) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * {
    color: var(--text) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background-color: var(--bg1) !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    color: var(--textdim) !important;
    padding: 0.6rem 1.2rem !important;
    border-radius: 0 !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
    text-transform: uppercase !important;
}
.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom-color: var(--primary) !important;
    background: rgba(0, 229, 255, 0.04) !important;
}

/* ── Cards ── */
.sigma-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
}
.sigma-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--primary), transparent);
}

/* ── KPI tiles ── */
.kpi-tile {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1rem 1.25rem;
    text-align: center;
    position: relative;
}
.kpi-label {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--textdim);
    margin-bottom: 0.35rem;
}
.kpi-value {
    font-family: var(--mono);
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--primary);
    line-height: 1;
}
.kpi-value.success { color: var(--success); }
.kpi-value.warn    { color: var(--warn); }
.kpi-value.danger  { color: var(--danger); }
.kpi-sub {
    font-family: var(--mono);
    font-size: 0.65rem;
    color: var(--textdim);
    margin-top: 0.3rem;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    font-family: var(--mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.2rem 0.55rem;
    border-radius: 2px;
}
.badge-ok      { background: rgba(0,255,136,0.15); color: var(--success); border: 1px solid rgba(0,255,136,0.3); }
.badge-breach  { background: rgba(255,60,90,0.15);  color: var(--danger);  border: 1px solid rgba(255,60,90,0.3); }
.badge-warn    { background: rgba(255,170,0,0.15);  color: var(--warn);    border: 1px solid rgba(255,170,0,0.3); }
.badge-info    { background: rgba(0,229,255,0.12);  color: var(--primary); border: 1px solid rgba(0,229,255,0.25); }
.badge-active  { background: rgba(0,255,136,0.15); color: var(--success); border: 1px solid rgba(0,255,136,0.3); }
.badge-alarm   { background: rgba(255,60,90,0.15);  color: var(--danger);  border: 1px solid rgba(255,60,90,0.3); }

/* ── Agent timeline ── */
.agent-row {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--border);
}
.agent-icon {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; flex-shrink: 0;
    background: var(--bg3);
    border: 1px solid var(--border);
}
.agent-name {
    font-family: var(--mono);
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--primary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.agent-detail {
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--textdim);
    margin-top: 0.2rem;
    line-height: 1.6;
}

/* ── Timeline pulse dot ── */
.pulse-green {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 0 3px rgba(0,255,136,0.2);
    display: inline-block;
    margin-right: 0.4rem;
}

/* ── Section headers ── */
.section-header {
    font-family: var(--mono);
    font-size: 0.68rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--textdim);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: 1.25rem;
}

/* ── Report viewer ── */
.report-block {
    font-family: var(--mono);
    font-size: 0.74rem;
    line-height: 1.8;
    color: var(--text);
    background: var(--bg1);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1.25rem;
    white-space: pre-wrap;
    overflow-x: auto;
    max-height: 500px;
    overflow-y: auto;
}

/* ── Metrics bar ── */
.progress-bar-outer {
    background: var(--bg3);
    border-radius: 2px;
    height: 6px;
    overflow: hidden;
    margin: 0.3rem 0;
}
.progress-bar-inner {
    height: 100%;
    border-radius: 2px;
    transition: width 0.6s ease;
}

/* ── Tool audit row ── */
.tool-row {
    display: grid;
    grid-template-columns: 1.5fr 2fr 1fr 80px 80px;
    gap: 1rem;
    padding: 0.6rem 1rem;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 0.68rem;
    align-items: center;
}
.tool-row:hover { background: var(--bg3); }

/* ── Override streamlit defaults ── */
.stDataFrame { border: 1px solid var(--border) !important; }
.stDataFrame thead th {
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    background: var(--bg3) !important;
    color: var(--textdim) !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    color: var(--primary) !important;
}
.stSelectbox label, .stTextInput label, .stDateInput label {
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--textdim) !important;
}
input, select, textarea {
    background-color: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
}
.stButton > button {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    background: transparent !important;
    border: 1px solid var(--primary) !important;
    color: var(--primary) !important;
    border-radius: 2px !important;
    padding: 0.4rem 1rem !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: rgba(0,229,255,0.08) !important;
}
hr { border-color: var(--border) !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# PLOTLY THEME
# ─────────────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color="#c8daf0", size=11),
    xaxis=dict(gridcolor="#1e3050", zerolinecolor="#1e3050"),
    yaxis=dict(gridcolor="#1e3050", zerolinecolor="#1e3050"),
    colorway=["#00e5ff", "#00ff88", "#ffaa00", "#ff3c5a", "#b97aff"],
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    margin=dict(l=10, r=10, t=30, b=10),
)


# ─────────────────────────────────────────────────────────────
# AWS / SNOWFLAKE CONNECTION HELPERS
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_s3_client():
    try:
        return boto3.client(
            "s3",
            region_name=st.secrets["aws"]["region"],
            aws_access_key_id=st.secrets["aws"]["access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["secret_access_key"],
        )
    except Exception:
        return None


@st.cache_resource
def get_cloudwatch_client():
    try:
        return boto3.client(
            "cloudwatch",
            region_name=st.secrets["aws"]["region"],
            aws_access_key_id=st.secrets["aws"]["access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["secret_access_key"],
        )
    except Exception:
        return None


@st.cache_resource
def get_logs_client():
    try:
        return boto3.client(
            "logs",
            region_name=st.secrets["aws"]["region"],
            aws_access_key_id=st.secrets["aws"]["access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["secret_access_key"],
        )
    except Exception:
        return None


def get_snowflake_connection():
    try:
        import snowflake.connector
        return snowflake.connector.connect(
            account=st.secrets["snowflake"]["account"],
            user=st.secrets["snowflake"]["user"],
            password=st.secrets["snowflake"]["password"],
            database=st.secrets["snowflake"]["database"],
            schema=st.secrets["snowflake"].get("schema", "SILVER"),
            warehouse=st.secrets["snowflake"]["warehouse"],
        )
    except Exception:
        return None


def s3_bucket():
    try:
        return st.secrets["aws"]["s3_bucket"]
    except Exception:
        return "sigma-datatech-demo"


# ─────────────────────────────────────────────────────────────
# DATA LOADERS
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_incident_reports():
    """Load all incident report files from S3 reports/ prefix."""
    s3 = get_s3_client()
    bucket = s3_bucket()
    reports = []
    if s3:
        try:
            resp = s3.list_objects_v2(Bucket=bucket, Prefix="reports/")
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if not key.endswith("/"):
                    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
                    reports.append({
                        "key": key,
                        "filename": key.split("/")[-1],
                        "last_modified": obj["LastModified"],
                        "size_kb": round(obj["Size"] / 1024, 1),
                        "content": body,
                    })
        except Exception as e:
            st.toast(f"S3 reports error: {e}", icon="⚠️")

    # Demo fallback
    if not reports:
        reports = get_demo_reports()
    return sorted(reports, key=lambda x: x["last_modified"], reverse=True)


@st.cache_data(ttl=60)
def load_quarantine_data():
    """Load quarantined records from S3 quarantine/ prefix."""
    s3 = get_s3_client()
    bucket = s3_bucket()
    rows = []
    if s3:
        try:
            resp = s3.list_objects_v2(Bucket=bucket, Prefix="quarantine/")
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if not key.endswith("/"):
                    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
                    try:
                        for line in body.strip().splitlines():
                            record = json.loads(line)
                            record["_s3_key"] = key
                            record["_ts"] = obj["LastModified"]
                            rows.append(record)
                    except Exception:
                        rows.append({"raw": body[:200], "_s3_key": key, "_ts": obj["LastModified"]})
        except Exception:
            pass

    if not rows:
        rows = get_demo_quarantine()
    return pd.DataFrame(rows)


@st.cache_data(ttl=30)
def load_cloudwatch_alarms():
    """Fetch CloudWatch alarms with prefix sigma-."""
    cw = get_cloudwatch_client()
    alarms = []
    if cw:
        try:
            resp = cw.describe_alarms(AlarmNamePrefix="sigma-")
            for a in resp.get("MetricAlarms", []):
                alarms.append({
                    "name": a["AlarmName"],
                    "state": a["StateValue"],
                    "metric": a.get("MetricName", "—"),
                    "threshold": a.get("Threshold", "—"),
                    "comparison": a.get("ComparisonOperator", "—").replace("GreaterThanOrEqualToThreshold", "≥").replace("LessThanThreshold", "<"),
                    "description": a.get("AlarmDescription", ""),
                    "updated": a.get("StateUpdatedTimestamp", ""),
                    "namespace": a.get("Namespace", ""),
                })
        except Exception:
            pass
    if not alarms:
        alarms = get_demo_alarms()
    return alarms


@st.cache_data(ttl=60)
def load_snowflake_metrics():
    """Query Snowflake for load summary metrics."""
    conn = get_snowflake_connection()
    metrics = {}
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*)            AS total_rows,
                    SUM(amount)         AS gmv,
                    COUNT(DISTINCT merchant_name) AS merchants,
                    MAX(created_at)     AS latest_row
                FROM SIGMA.SILVER.TRANSACTIONS
                WHERE transaction_date = CURRENT_DATE()
            """)
            row = cur.fetchone()
            if row:
                metrics = {
                    "total_rows": row[0],
                    "gmv": row[1],
                    "merchants": row[2],
                    "latest_row": str(row[3]),
                }

            cur.execute("""
                SELECT transaction_date, COUNT(*) as cnt, SUM(amount) as gmv
                FROM SIGMA.SILVER.TRANSACTIONS
                WHERE transaction_date >= DATEADD(day, -7, CURRENT_DATE())
                GROUP BY 1 ORDER BY 1
            """)
            history = cur.fetchall()
            metrics["history"] = [{"date": str(r[0]), "rows": r[1], "gmv": r[2]} for r in history]
            conn.close()
        except Exception as e:
            metrics["error"] = str(e)
    if not metrics or "error" in metrics:
        metrics = get_demo_snowflake_metrics()
    return metrics


# ─────────────────────────────────────────────────────────────
# REPORT PARSER
# ─────────────────────────────────────────────────────────────
def parse_report(content: str) -> dict:
    """Extract structured fields from a markdown incident report."""
    data = {
        "title": "",
        "summary": "",
        "timeline_lines": [],
        "root_cause": "",
        "business_impact": {},
        "fix_applied": [],
        "prevention": [],
        "raw": content,
    }
    lines = content.splitlines()
    current_section = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            data["title"] = stripped[2:]
        elif stripped.startswith("## "):
            current_section = stripped[3:].lower().replace(" ", "_")
        elif current_section == "summary" and stripped:
            data["summary"] += stripped + " "
        elif current_section == "timeline" and stripped and not stripped.startswith("#"):
            data["timeline_lines"].append(stripped)
        elif current_section == "root_cause" and stripped:
            data["root_cause"] += stripped + " "
        elif current_section in ("business_impact", "fix_applied", "prevention") and stripped:
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                if current_section == "business_impact":
                    data["business_impact"][k.strip()] = v.strip()
                elif current_section == "fix_applied":
                    data["fix_applied"].append(stripped)
                elif current_section == "prevention":
                    data["prevention"].append(stripped)
            else:
                if current_section == "fix_applied":
                    data["fix_applied"].append(stripped)
                elif current_section == "prevention":
                    data["prevention"].append(stripped)

    # Extract key numbers with regex
    gmv_match = re.search(r"₹([\d,]+)", content)
    if gmv_match:
        data["gmv_loss"] = gmv_match.group(0)
    records_match = re.search(r"(\d+)\s+records?\s+(missing|lost|unloaded)", content, re.IGNORECASE)
    if records_match:
        data["records_lost"] = records_match.group(1)
    sla_breach = "breach" in content.lower() or "breached" in content.lower()
    data["sla_breach"] = sla_breach

    return data


def extract_sla_table(report_content: str) -> list:
    """Parse SLA findings from report text into rows."""
    rows = []
    patterns = [
        r"([\w\s]+?)\s+(?:threshold|SLA)\s+₹([\d,]+).*?₹([\d,]+)\s+missing",
        r"([\w]+)\s+—\s+₹([\d,]+)\s+missing\s+\(threshold\s+₹([\d,]+)\)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, report_content, re.IGNORECASE):
            merchant = m.group(1).strip()
            threshold = m.group(2).replace(",", "")
            actual = m.group(3).replace(",", "")
            breach = int(actual) > int(threshold)
            rows.append({
                "Merchant": merchant,
                "SLA Threshold (₹)": f"₹{int(threshold):,}",
                "Actual Loss (₹)": f"₹{int(actual):,}",
                "Status": "BREACH" if breach else "OK",
            })

    # Demo SLA rows if none found
    if not rows and report_content:
        rows = [
            {"Merchant": "QuickMart", "SLA Threshold (₹)": "₹50,000", "Actual Loss (₹)": "₹1,21,450", "Status": "BREACH"},
            {"Merchant": "FuelPlus",  "SLA Threshold (₹)": "₹1,00,000", "Actual Loss (₹)": "₹87,200",  "Status": "OK"},
            {"Merchant": "TechZone",  "SLA Threshold (₹)": "₹75,000", "Actual Loss (₹)": "₹31,000",  "Status": "OK"},
        ]
    return rows


# ─────────────────────────────────────────────────────────────
# DEMO / FALLBACK DATA
# ─────────────────────────────────────────────────────────────
def get_demo_reports():
    ts = datetime.now(timezone.utc)
    return [
        {
            "key": "reports/incident_20260604_133127.md",
            "filename": "incident_20260604_133127.md",
            "last_modified": ts,
            "size_kb": 4.2,
            "content": """# Incident Report — ₹4.72L GMV Loss — 2026-06-04

## Summary
Silent pipeline failure. 847 transactions unloaded. ₹4,72,340 GMV missing. QuickMart SLA breach confirmed. Root cause: Lambda v2 deploy at 02:11 UTC.

## Timeline
02:11 UTC  Lambda sigma-kinesis-producer auto-deployed to v2
02:11 UTC  v2 outputs merchant_nm (not merchant_name) + DD-MM-YYYY dates
02:12 UTC  Firehose delivers malformed JSON to S3
02:12 UTC  Snowflake COPY INTO runs — loads 0 rows (schema mismatch)
02:12 UTC  Existing CloudWatch alarm does not fire (threshold too high)
09:03 UTC  Business analyst notices ₹0 GMV on dashboard
09:03 UTC  Supervisor agent triggered
09:03:28 UTC  Pipeline fully restored. 3 new alarms active.

## Root Cause
Lambda v2 changed two things without a data contract review:
  1. Field name: merchant_name → merchant_nm
  2. Date format: YYYY-MM-DD → DD-MM-YYYY
Snowflake schema inference failed silently on both changes. No alarm existed for zero-row loads.

## Business Impact
Records lost:     847 transactions (02:11–02:15 UTC)
GMV gap:          ₹4,72,340
SLA breach:       QuickMart — ₹1,21,450 missing (threshold ₹50,000)
SLA ok:           FuelPlus — ₹87,200 missing (threshold ₹1,00,000)
Notification due: Merchant relations team within 2 hours of detection

## Fix Applied
13:31:11 UTC  Lambda rolled back to v1 (stable)
13:31:15 UTC  824 records replayed from Kinesis with field mapping + date fix
13:31:17 UTC  23 records quarantined (null transaction_ids — separate issue)
13:31:18 UTC  Snowflake GMV restored to ₹4,69,890

## Prevention
3 CloudWatch alarms created and active:
  sigma-snowflake-zero-load        → fires if COPY INTO loads 0 rows twice
  sigma-lambda-version-change      → fires on any Lambda alias change
  sigma-pipeline-row-divergence    → fires if Kinesis/Snowflake row gap > 5%
Recommended: Lambda deploy policy requiring canary traffic (10% for 5 min)
""",
        },
        {
            "key": "reports/incident_20260520_091500.md",
            "filename": "incident_20260520_091500.md",
            "last_modified": ts - timedelta(days=15),
            "size_kb": 3.1,
            "content": """# Incident Report — ₹1.8L GMV Loss — 2026-05-20

## Summary
Kinesis shard iterator expiry caused 3-hour gap. 312 records unloaded. ₹1,82,000 GMV missing. No SLA breach.

## Timeline
03:00 UTC  Kinesis shard iterator expired (24h limit)
03:00 UTC  Lambda failed to get new iterator — silent retry loop
06:30 UTC  On-call engineer noticed gap
06:45 UTC  Supervisor agent triggered
06:46:10 UTC  Records replayed. Iterator refresh added to runbook.

## Root Cause
Kinesis GetShardIterator not refreshed within 24 hours. Lambda consumer held stale iterator.

## Business Impact
Records lost:     312 transactions
GMV gap:          ₹1,82,000
SLA breach:       None (all merchants below threshold)

## Fix Applied
06:45:50 UTC  Lambda restarted with fresh shard iterator
06:45:55 UTC  299 records replayed (13 quarantined — malformed amounts)
06:46:00 UTC  Snowflake row count verified

## Prevention
1 CloudWatch alarm created: sigma-kinesis-iterator-age > 3600s
""",
        },
    ]


def get_demo_quarantine():
    return [
        {"transaction_id": None, "merchant_name": "QuickMart", "amount": 450.0,  "reason": "null_transaction_id",  "timestamp": "2026-06-04T02:13:01Z"},
        {"transaction_id": None, "merchant_name": "FuelPlus",  "amount": 892.5,  "reason": "null_transaction_id",  "timestamp": "2026-06-04T02:13:03Z"},
        {"transaction_id": "T-991", "merchant_name": "TechZone", "amount": -50.0, "reason": "negative_amount",     "timestamp": "2026-06-04T02:13:05Z"},
        {"transaction_id": "T-992", "merchant_name": "QuickMart","amount": 0,     "reason": "zero_amount",          "timestamp": "2026-06-04T02:13:08Z"},
        {"transaction_id": "T-993", "merchant_name": "FuelPlus", "amount": 120.0, "reason": "schema_mismatch",      "timestamp": "2026-06-04T02:13:11Z"},
        {"transaction_id": "T-994", "merchant_name": "QuickMart","amount": 750.0, "reason": "duplicate",            "timestamp": "2026-06-04T02:13:14Z"},
        {"transaction_id": None,    "merchant_name": "TechZone", "amount": 300.0, "reason": "null_transaction_id",  "timestamp": "2026-06-04T02:13:17Z"},
        {"transaction_id": "T-995", "merchant_name": "FuelPlus", "amount": 99.9,  "reason": "schema_mismatch",      "timestamp": "2026-06-04T02:13:20Z"},
        {"transaction_id": "T-996", "merchant_name": "QuickMart","amount": 450.0, "reason": "duplicate",            "timestamp": "2026-06-04T02:13:22Z"},
        {"transaction_id": None,    "merchant_name": "TechZone", "amount": 670.0, "reason": "null_transaction_id",  "timestamp": "2026-06-04T02:13:25Z"},
        {"transaction_id": "T-997", "merchant_name": "FuelPlus", "amount": 210.0, "reason": "schema_mismatch",      "timestamp": "2026-06-04T02:13:28Z"},
        {"transaction_id": "T-998", "merchant_name": "QuickMart","amount": 88.0,  "reason": "duplicate",            "timestamp": "2026-06-04T02:13:31Z"},
        {"transaction_id": None,    "merchant_name": "QuickMart","amount": 540.0, "reason": "null_transaction_id",  "timestamp": "2026-06-04T02:13:34Z"},
    ]


def get_demo_alarms():
    return [
        {"name": "sigma-snowflake-zero-load",     "state": "OK",     "metric": "RowsLoaded",      "threshold": 0,   "comparison": "≤",  "description": "Fires if COPY INTO loads 0 rows twice consecutively", "namespace": "Sigma/Pipeline", "updated": datetime.now(timezone.utc) - timedelta(hours=2)},
        {"name": "sigma-lambda-version-change",   "state": "ALARM",  "metric": "ConfigChange",    "threshold": 1,   "comparison": "≥",  "description": "Fires on any Lambda alias change to sigma-kinesis-producer", "namespace": "AWS/Lambda", "updated": datetime.now(timezone.utc) - timedelta(hours=6)},
        {"name": "sigma-pipeline-row-divergence", "state": "OK",     "metric": "RowDivergencePct","threshold": 5,   "comparison": "≥",  "description": "Fires if Kinesis→Snowflake row count gap exceeds 5%", "namespace": "Sigma/Pipeline", "updated": datetime.now(timezone.utc) - timedelta(hours=1)},
    ]


def get_demo_snowflake_metrics():
    today = datetime.now().date()
    history = []
    base_rows = 118000
    for i in range(7, 0, -1):
        d = today - timedelta(days=i)
        rows = base_rows + (0 if i == 1 else 2000 * (7 - i))
        history.append({"date": str(d), "rows": rows, "gmv": rows * 3.95})
    # Day 12 incident day — only 40k loaded initially
    history.append({"date": str(today), "rows": 40823, "gmv": 40823 * 3.95})
    return {
        "total_rows": 40823,
        "gmv": 161251.85,
        "merchants": 3,
        "latest_row": datetime.now().isoformat(),
        "history": history,
        "quarantined": 23,
        "recovered": 824,
        "rejected": 0,
    }


def get_demo_agent_events():
    base = datetime(2026, 6, 4, 13, 31, 2, tzinfo=timezone.utc)
    return [
        {"t": base,                          "agent": "SUPERVISOR",      "icon": "⚡", "event": "Incident received. Dashboard gap: 80,000 records missing since 02:00 UTC. Discovering tools via MCP server…"},
        {"t": base + timedelta(seconds=1),   "agent": "SUPERVISOR",      "icon": "⚡", "event": "9 tools discovered. Querying knowledge base for similar incidents → 0 matches (first occurrence). Delegating to Forensics + Impact in parallel."},
        {"t": base + timedelta(seconds=3),   "agent": "FORENSICS",       "icon": "🔬", "event": "Checking CloudWatch: Lambda sigma-kinesis-producer version changed at 02:11 UTC. v1→v2 deploy detected."},
        {"t": base + timedelta(seconds=5),   "agent": "FORENSICS",       "icon": "🔬", "event": "v2 outputs merchant_nm (not merchant_name) + DD-MM-YYYY dates. Snowflake COPY INTO loaded 0 rows. Root cause confirmed."},
        {"t": base + timedelta(seconds=3),   "agent": "IMPACT",          "icon": "📊", "event": "Snowflake row count gap confirmed: 847 records in Kinesis, 0 loaded. Querying SLA contracts from Knowledge Base…"},
        {"t": base + timedelta(seconds=6),   "agent": "IMPACT",          "icon": "📊", "event": "GMV impact: ₹4,72,340. QuickMart SLA ₹50K threshold → BREACHED (₹1,21,450). FuelPlus ₹1L threshold → not breached (₹87,200)."},
        {"t": base + timedelta(seconds=8),   "agent": "SUPERVISOR",      "icon": "⚡", "event": "Root cause + impact confirmed. Delegating to Recovery + Rollback in parallel."},
        {"t": base + timedelta(seconds=9),   "agent": "ROLLBACK",        "icon": "↩️", "event": "Lambda alias LIVE → pointing to v1. Rollback initiated…"},
        {"t": base + timedelta(seconds=11),  "agent": "ROLLBACK",        "icon": "↩️", "event": "Rollback complete. Sent 5 test records → all loaded to Snowflake. v1 confirmed stable."},
        {"t": base + timedelta(seconds=9),   "agent": "RECOVERY",        "icon": "🔄", "event": "Getting Kinesis shard iterator at 02:11:07 UTC. Retrieved 847 records from shardId-000000000000."},
        {"t": base + timedelta(seconds=12),  "agent": "RECOVERY",        "icon": "🔄", "event": "Applying field mapping: merchant_nm→merchant_name, DD-MM-YYYY→YYYY-MM-DD. Running quality checks…"},
        {"t": base + timedelta(seconds=14),  "agent": "RECOVERY",        "icon": "🔄", "event": "824 clean records loaded. 23 quarantined (null transaction_ids). Idempotency check: 0 duplicates. GMV restored: ₹4,69,890."},
        {"t": base + timedelta(seconds=16),  "agent": "SUPERVISOR",      "icon": "⚡", "event": "Pipeline restored. Delegating to Hardening Agent."},
        {"t": base + timedelta(seconds=17),  "agent": "HARDENING",       "icon": "🛡️", "event": "Creating alarm: sigma-snowflake-zero-load → Active."},
        {"t": base + timedelta(seconds=19),  "agent": "HARDENING",       "icon": "🛡️", "event": "Creating alarm: sigma-lambda-version-change → Active."},
        {"t": base + timedelta(seconds=21),  "agent": "HARDENING",       "icon": "🛡️", "event": "Creating alarm: sigma-pipeline-row-divergence → Active. 3/3 alarms live in account."},
        {"t": base + timedelta(seconds=22),  "agent": "SUPERVISOR",      "icon": "⚡", "event": "Hardening complete. Delegating to Incident Report Agent."},
        {"t": base + timedelta(seconds=23),  "agent": "INCIDENT REPORT", "icon": "📋", "event": "Compiling findings from all 5 agents. Writing CTO-ready post-mortem to S3…"},
        {"t": base + timedelta(seconds=26),  "agent": "INCIDENT REPORT", "icon": "📋", "event": "Report written → s3://sigma-datatech/reports/incident_20260604_133127.md. SNS alert sent."},
        {"t": base + timedelta(seconds=26),  "agent": "SUPERVISOR",      "icon": "⚡", "event": "✅ RECOVERY COMPLETE | 26s | GMV ₹4,69,890 restored | 6 agents | 14 tool calls | 0 human interventions"},
    ]


def get_demo_tools():
    return [
        {"Tool": "check_cloudwatch_metrics", "Parameters": "Lambda, last_8h",          "Result": "Version change at 02:11 UTC",       "Time (ms)": 340, "Status": "OK"},
        {"Tool": "get_kinesis_records",      "Parameters": "shard-000, ts=02:11:07",    "Result": "847 records retrieved",             "Time (ms)": 890, "Status": "OK"},
        {"Tool": "query_snowflake",          "Parameters": "COUNT(*) TRANSACTIONS",     "Result": "40,823 rows (expected 120,000)",    "Time (ms)": 620, "Status": "OK"},
        {"Tool": "query_snowflake",          "Parameters": "SLA contract lookup",       "Result": "QuickMart ₹50K threshold found",   "Time (ms)": 410, "Status": "OK"},
        {"Tool": "rollback_lambda_version",  "Parameters": "sigma-kinesis-producer v1", "Result": "Alias LIVE → v1 in 8s",           "Time (ms)": 8120,"Status": "OK"},
        {"Tool": "quarantine_rows",          "Parameters": "23 null_transaction_id",    "Result": "Written to S3 quarantine/",        "Time (ms)": 230, "Status": "OK"},
        {"Tool": "load_to_snowflake",        "Parameters": "824 mapped records",        "Result": "824 rows loaded, 0 duplicates",    "Time (ms)": 1850,"Status": "OK"},
        {"Tool": "create_cloudwatch_alarm",  "Parameters": "sigma-snowflake-zero-load", "Result": "Alarm created, state: OK",         "Time (ms)": 480, "Status": "OK"},
        {"Tool": "create_cloudwatch_alarm",  "Parameters": "sigma-lambda-version-change","Result": "Alarm created, state: ALARM",     "Time (ms)": 460, "Status": "OK"},
        {"Tool": "create_cloudwatch_alarm",  "Parameters": "sigma-pipeline-row-divergence","Result": "Alarm created, state: OK",      "Time (ms)": 450, "Status": "OK"},
        {"Tool": "write_incident_report",    "Parameters": "incident_20260604_133127.md","Result": "Written to S3 reports/",          "Time (ms)": 310, "Status": "OK"},
        {"Tool": "send_sns_alert",           "Parameters": "sigma-alerts topic",        "Result": "MessageId: abc-123 delivered",     "Time (ms)": 180, "Status": "OK"},
        {"Tool": "check_cloudwatch_metrics", "Parameters": "Kinesis throttles, last_1h","Result": "0 throttle events",               "Time (ms)": 290, "Status": "OK"},
        {"Tool": "query_snowflake",          "Parameters": "Verify row count post-load","Result": "120,647 rows. GMV ₹4,69,890",     "Time (ms)": 530, "Status": "OK"},
    ]


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 0.5rem 0 1.5rem 0;">
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;letter-spacing:0.2em;
                    text-transform:uppercase;color:#4a6080;margin-bottom:0.5rem;">
            Sigma DataTech
        </div>
        <div style="font-family:'Sora',sans-serif;font-size:1.25rem;font-weight:800;
                    color:#00e5ff;line-height:1.1;">
            Intelligence<br>Platform
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#4a6080;
                    margin-top:0.4rem;">
            7-AGENT SELF-HEALING PIPELINE
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">Live Status</div>', unsafe_allow_html=True)
    pipeline_ok = True
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:0.5rem;
                font-family:'JetBrains Mono',monospace;font-size:0.72rem;margin-bottom:0.5rem;">
        <span class="pulse-green"></span>
        <span style="color:#00ff88;">Pipeline Healthy</span>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#4a6080;">
        Agents: Standby<br>
        Last incident: 26s recovery<br>
        Alarms: 3 active
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Controls</div>', unsafe_allow_html=True)
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)
    if st.button("⟳  Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Configuration</div>', unsafe_allow_html=True)
    try:
        bucket_name = s3_bucket()
        st.markdown(f"""
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;line-height:2;color:#6b85a0;">
            S3 Bucket<br>
            <span style="color:#c8daf0;">{bucket_name}</span><br><br>
            Region<br>
            <span style="color:#c8daf0;">{st.secrets.get('aws', {}).get('region', 'us-east-1')}</span><br><br>
            Snowflake<br>
            <span style="color:#c8daf0;">{st.secrets.get('snowflake', {}).get('account', '—')}</span>
        </div>
        """, unsafe_allow_html=True)
    except Exception:
        st.markdown("""
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#ffaa00;">
            ⚠ Demo Mode<br>
            <span style="color:#6b85a0;">Add secrets to connect live AWS + Snowflake</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#4a6080;">
        Day 12 · AWS Bedrock<br>
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div style="border-bottom:1px solid #1e3050;padding-bottom:1.25rem;margin-bottom:1.5rem;">
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;
                letter-spacing:0.18em;text-transform:uppercase;color:#4a6080;margin-bottom:0.4rem;">
        Sigma Intelligence Platform · Command Center
    </div>
    <h1 style="font-family:'Sora',sans-serif;font-size:1.8rem;font-weight:800;
               color:#c8daf0;margin:0;line-height:1.15;">
        Self-Healing Pipeline <span style="color:#00e5ff;">Dashboard</span>
    </h1>
</div>
""", unsafe_allow_html=True)

# KPI Row
reports = load_incident_reports()
qdf = load_quarantine_data()
alarms = load_cloudwatch_alarms()
sf = load_snowflake_metrics()

active_alarms = sum(1 for a in alarms if a["state"] == "ALARM")
breach_alarms = active_alarms

kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

with kpi1:
    st.markdown("""
    <div class="kpi-tile">
        <div class="kpi-label">Total Incidents</div>
        <div class="kpi-value">""" + str(len(reports)) + """</div>
        <div class="kpi-sub">all time</div>
    </div>""", unsafe_allow_html=True)

with kpi2:
    gmv = sf.get("gmv", 0) or 0
    st.markdown(f"""
    <div class="kpi-tile">
        <div class="kpi-label">GMV Today</div>
        <div class="kpi-value success">₹{gmv:,.0f}</div>
        <div class="kpi-sub">{sf.get('total_rows', 0):,} rows</div>
    </div>""", unsafe_allow_html=True)

with kpi3:
    recovered = sf.get("recovered", 824)
    st.markdown(f"""
    <div class="kpi-tile">
        <div class="kpi-label">Records Recovered</div>
        <div class="kpi-value success">{recovered:,}</div>
        <div class="kpi-sub">last incident</div>
    </div>""", unsafe_allow_html=True)

with kpi4:
    qcount = len(qdf) if not qdf.empty else 0
    st.markdown(f"""
    <div class="kpi-tile">
        <div class="kpi-label">Quarantined</div>
        <div class="kpi-value warn">{qcount}</div>
        <div class="kpi-sub">records</div>
    </div>""", unsafe_allow_html=True)

with kpi5:
    alarm_color = "danger" if active_alarms > 0 else "success"
    st.markdown(f"""
    <div class="kpi-tile">
        <div class="kpi-label">Alarm State</div>
        <div class="kpi-value {alarm_color}">{active_alarms} FIRING</div>
        <div class="kpi-sub">{len(alarms)} total alarms</div>
    </div>""", unsafe_allow_html=True)

with kpi6:
    st.markdown("""
    <div class="kpi-tile">
        <div class="kpi-label">Recovery Time</div>
        <div class="kpi-value">26s</div>
        <div class="kpi-sub">last incident · 0 humans</div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────
tabs = st.tabs([
    "⚡ Agent Timeline",
    "📋 Incident Reports",
    "⚠️ SLA Monitor",
    "🗑️ Quarantine",
    "🔧 Tool Audit",
    "❄️ Snowflake",
    "🔔 Alarms",
    "🕸️ Agent Graph",
    "🔍 Search",
])


# ══════════════════════════════════════════════════════════════
# TAB 1 — AGENT EXECUTION TIMELINE
# ══════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-header">Agent Execution Log — Last Incident</div>', unsafe_allow_html=True)

    agent_events = get_demo_agent_events()
    agent_colors = {
        "SUPERVISOR":      "#00e5ff",
        "FORENSICS":       "#b97aff",
        "IMPACT":          "#ffaa00",
        "RECOVERY":        "#00ff88",
        "ROLLBACK":        "#ff6b35",
        "HARDENING":       "#ff3c5a",
        "INCIDENT REPORT": "#4fc3f7",
    }

    for ev in agent_events:
        color = agent_colors.get(ev["agent"], "#c8daf0")
        ts = ev["t"].strftime("%H:%M:%S")
        st.markdown(f"""
        <div class="agent-row">
            <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;
                        color:#4a6080;min-width:60px;padding-top:0.15rem;">{ts}</div>
            <div class="agent-icon" style="border-color:{color}33;">
                {ev['icon']}
            </div>
            <div>
                <div class="agent-name" style="color:{color};">{ev['agent']}</div>
                <div class="agent-detail">{ev['event']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Gantt-style agent timeline
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">Agent Execution Gantt</div>', unsafe_allow_html=True)

    gantt_data = [
        {"Agent": "Forensics",       "Start": 3,  "End": 9,  "Color": "#b97aff"},
        {"Agent": "Impact",          "Start": 3,  "End": 10, "Color": "#ffaa00"},
        {"Agent": "Rollback",        "Start": 9,  "End": 15, "Color": "#ff6b35"},
        {"Agent": "Recovery",        "Start": 9,  "End": 18, "Color": "#00ff88"},
        {"Agent": "Hardening",       "Start": 17, "End": 24, "Color": "#ff3c5a"},
        {"Agent": "Incident Report", "Start": 23, "End": 26, "Color": "#4fc3f7"},
    ]
    fig = go.Figure()
    for i, ag in enumerate(gantt_data):
        fig.add_trace(go.Bar(
            y=[ag["Agent"]],
            x=[ag["End"] - ag["Start"]],
            base=[ag["Start"]],
            orientation="h",
            marker=dict(color=ag["Color"], opacity=0.85, line=dict(width=0)),
            name=ag["Agent"],
            hovertemplate=f"<b>{ag['Agent']}</b><br>Start: {ag['Start']}s → End: {ag['End']}s<br>Duration: {ag['End']-ag['Start']}s<extra></extra>",
        ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        showlegend=False,
        xaxis_title="Seconds from incident trigger",
        height=280,
        barmode="overlay",
    )
    fig.add_vline(x=26, line_dash="dot", line_color="#00ff88", annotation_text="Recovery complete (26s)")
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# TAB 2 — INCIDENT REPORTS
# ══════════════════════════════════════════════════════════════
with tabs[1]:
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown('<div class="section-header">All Reports</div>', unsafe_allow_html=True)
        report_labels = [r["filename"] for r in reports]
        selected_idx = st.radio("", report_labels, label_visibility="collapsed")
        sel_report = next(r for r in reports if r["filename"] == selected_idx)

        st.markdown(f"""
        <div class="sigma-card" style="margin-top:1rem;">
            <div class="kpi-label">File</div>
            <div style="font-family:var(--mono);font-size:0.7rem;color:#c8daf0;margin-top:0.2rem;">
                {sel_report['filename']}
            </div>
            <div class="kpi-label" style="margin-top:0.75rem;">Last Modified</div>
            <div style="font-family:var(--mono);font-size:0.7rem;color:#c8daf0;">
                {sel_report['last_modified'].strftime('%Y-%m-%d %H:%M UTC') if hasattr(sel_report['last_modified'],'strftime') else sel_report['last_modified']}
            </div>
            <div class="kpi-label" style="margin-top:0.75rem;">Size</div>
            <div style="font-family:var(--mono);font-size:0.7rem;color:#c8daf0;">
                {sel_report['size_kb']} KB
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Compare toggle
        if len(reports) > 1:
            st.markdown('<div class="section-header" style="margin-top:1rem;">Compare With</div>', unsafe_allow_html=True)
            compare_labels = ["None"] + [r["filename"] for r in reports if r["filename"] != selected_idx]
            compare_sel = st.selectbox("", compare_labels, label_visibility="collapsed")

    with col_right:
        parsed = parse_report(sel_report["content"])
        st.markdown('<div class="section-header">Report Details</div>', unsafe_allow_html=True)

        # SLA badge
        sla_badge = '<span class="badge badge-breach">⚠ SLA BREACH</span>' if parsed["sla_breach"] else '<span class="badge badge-ok">✓ No Breach</span>'
        st.markdown(f"""
        <div style="margin-bottom:1rem;">
            <div style="font-family:'Sora',sans-serif;font-size:1.1rem;font-weight:700;
                        color:#c8daf0;margin-bottom:0.5rem;">{parsed['title']}</div>
            {sla_badge}
            {f'<span class="badge badge-info" style="margin-left:0.5rem;">{parsed.get("gmv_loss","")}</span>' if parsed.get("gmv_loss") else ''}
            {f'<span class="badge badge-warn" style="margin-left:0.5rem;">{parsed.get("records_lost","")} records</span>' if parsed.get("records_lost") else ''}
        </div>
        """, unsafe_allow_html=True)

        r_tab1, r_tab2, r_tab3 = st.tabs(["Summary", "Timeline", "Raw"])

        with r_tab1:
            if parsed["summary"]:
                st.markdown(f"""
                <div class="sigma-card">
                    <div class="kpi-label">Summary</div>
                    <div style="font-family:var(--mono);font-size:0.72rem;line-height:1.8;
                                color:#c8daf0;margin-top:0.5rem;">{parsed['summary']}</div>
                </div>
                """, unsafe_allow_html=True)
            if parsed["root_cause"]:
                st.markdown(f"""
                <div class="sigma-card">
                    <div class="kpi-label">Root Cause</div>
                    <div style="font-family:var(--mono);font-size:0.72rem;line-height:1.8;
                                color:#ffaa00;margin-top:0.5rem;">{parsed['root_cause']}</div>
                </div>
                """, unsafe_allow_html=True)

            if parsed["business_impact"]:
                st.markdown('<div class="kpi-label" style="margin-top:0.5rem;">Business Impact</div>', unsafe_allow_html=True)
                impact_cols = st.columns(len(parsed["business_impact"]))
                for col, (k, v) in zip(impact_cols, parsed["business_impact"].items()):
                    color = "danger" if "breach" in v.lower() else "warn" if "₹" in v else ""
                    col.markdown(f"""
                    <div class="kpi-tile">
                        <div class="kpi-label">{k}</div>
                        <div style="font-family:var(--mono);font-size:0.8rem;font-weight:600;
                                    color:{'#ff3c5a' if 'breach' in v.lower() else '#c8daf0'};
                                    margin-top:0.25rem;">{v}</div>
                    </div>""", unsafe_allow_html=True)

            sla_rows = extract_sla_table(sel_report["content"])
            if sla_rows:
                st.markdown('<div class="kpi-label" style="margin-top:1rem;">SLA Status</div>', unsafe_allow_html=True)
                for row in sla_rows:
                    badge = '<span class="badge badge-breach">✗ BREACH</span>' if row["Status"] == "BREACH" else '<span class="badge badge-ok">✓ OK</span>'
                    st.markdown(f"""
                    <div style="display:flex;justify-content:space-between;align-items:center;
                                padding:0.5rem 0;border-bottom:1px solid #1e3050;">
                        <span style="font-family:var(--mono);font-size:0.72rem;color:#c8daf0;">{row['Merchant']}</span>
                        <span style="font-family:var(--mono);font-size:0.68rem;color:#6b85a0;">Threshold: {row['SLA Threshold (₹)']}</span>
                        <span style="font-family:var(--mono);font-size:0.68rem;color:#ffaa00;">Loss: {row['Actual Loss (₹)']}</span>
                        {badge}
                    </div>
                    """, unsafe_allow_html=True)

        with r_tab2:
            if parsed["timeline_lines"]:
                for line in parsed["timeline_lines"]:
                    parts = line.split("  ", 1)
                    ts_part = parts[0] if parts else ""
                    ev_part = parts[1] if len(parts) > 1 else line
                    st.markdown(f"""
                    <div style="display:flex;gap:1rem;padding:0.4rem 0;
                                border-bottom:1px solid #1e3050;align-items:flex-start;">
                        <span style="font-family:var(--mono);font-size:0.65rem;color:#4a6080;
                                     min-width:90px;flex-shrink:0;">{ts_part}</span>
                        <span style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;">{ev_part}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No timeline data parsed from this report.")

        with r_tab3:
            st.markdown(f'<div class="report-block">{sel_report["content"]}</div>', unsafe_allow_html=True)

        # Compare view
        if len(reports) > 1 and "compare_sel" in dir() and compare_sel != "None":
            comp_report = next((r for r in reports if r["filename"] == compare_sel), None)
            if comp_report:
                st.markdown('<hr>', unsafe_allow_html=True)
                st.markdown('<div class="section-header">Comparison</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                comp_parsed = parse_report(comp_report["content"])
                with c1:
                    st.markdown(f"**{sel_report['filename']}**")
                    st.markdown(f"<span class='badge badge-info'>{parsed.get('gmv_loss','—')}</span>", unsafe_allow_html=True)
                    st.markdown(f"`{parsed['summary'][:300]}...`")
                with c2:
                    st.markdown(f"**{comp_report['filename']}**")
                    st.markdown(f"<span class='badge badge-info'>{comp_parsed.get('gmv_loss','—')}</span>", unsafe_allow_html=True)
                    st.markdown(f"`{comp_parsed['summary'][:300]}...`")


# ══════════════════════════════════════════════════════════════
# TAB 3 — SLA MONITOR
# ══════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-header">SLA Contract Breach Monitor</div>', unsafe_allow_html=True)

    sla_data = []
    for r in reports:
        rows = extract_sla_table(r["content"])
        for row in rows:
            row["Incident"] = r["filename"]
            row["Date"] = r["last_modified"].strftime("%Y-%m-%d") if hasattr(r["last_modified"], "strftime") else str(r["last_modified"])[:10]
            sla_data.append(row)

    if not sla_data:
        sla_data = extract_sla_table("")
        for row in sla_data:
            row["Incident"] = "incident_20260604_133127.md"
            row["Date"] = "2026-06-04"

    breach_count = sum(1 for r in sla_data if r["Status"] == "BREACH")
    ok_count     = sum(1 for r in sla_data if r["Status"] == "OK")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">Total SLA Checks</div>
            <div class="kpi-value">{len(sla_data)}</div>
        </div>""", unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">Breaches</div>
            <div class="kpi-value danger">{breach_count}</div>
        </div>""", unsafe_allow_html=True)
    with sc3:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">Compliant</div>
            <div class="kpi-value success">{ok_count}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # SLA table with colored rows
    st.markdown('<div class="section-header">SLA Detail Table</div>', unsafe_allow_html=True)
    header_cols = st.columns([1.2, 1.2, 1.2, 1, 1.5, 0.8])
    for col, label in zip(header_cols, ["Merchant", "Threshold", "Actual Loss", "Date", "Incident", "Status"]):
        col.markdown(f"<div style='font-family:var(--mono);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;color:#4a6080;'>{label}</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:1px;background:#1e3050;margin:0.4rem 0;'></div>", unsafe_allow_html=True)
    for row in sla_data:
        is_breach = row["Status"] == "BREACH"
        row_color = "rgba(255,60,90,0.06)" if is_breach else "transparent"
        badge = '<span class="badge badge-breach">✗ BREACH</span>' if is_breach else '<span class="badge badge-ok">✓ OK</span>'
        row_cols = st.columns([1.2, 1.2, 1.2, 1, 1.5, 0.8])
        with row_cols[0]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.72rem;color:#c8daf0;'>{row['Merchant']}</span>", unsafe_allow_html=True)
        with row_cols[1]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.72rem;color:#6b85a0;'>{row['SLA Threshold (₹)']}</span>", unsafe_allow_html=True)
        with row_cols[2]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.72rem;color:{'#ff3c5a' if is_breach else '#c8daf0'};font-weight:600;'>{row['Actual Loss (₹)']}</span>", unsafe_allow_html=True)
        with row_cols[3]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.68rem;color:#6b85a0;'>{row.get('Date','—')}</span>", unsafe_allow_html=True)
        with row_cols[4]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.65rem;color:#4a6080;'>{row.get('Incident','—')[:35]}</span>", unsafe_allow_html=True)
        with row_cols[5]:
            st.markdown(badge, unsafe_allow_html=True)
        st.markdown("<div style='height:1px;background:#132035;'></div>", unsafe_allow_html=True)

    # Bar chart — loss by merchant
    if sla_data:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">Loss by Merchant (₹)</div>', unsafe_allow_html=True)
        merchants = list({r["Merchant"] for r in sla_data})
        loss_vals = []
        threshold_vals = []
        for m in merchants:
            rows_m = [r for r in sla_data if r["Merchant"] == m]
            loss_val = int(rows_m[-1]["Actual Loss (₹)"].replace("₹","").replace(",","")) if rows_m else 0
            thresh_val = int(rows_m[-1]["SLA Threshold (₹)"].replace("₹","").replace(",","")) if rows_m else 0
            loss_vals.append(loss_val)
            threshold_vals.append(thresh_val)

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Actual Loss", x=merchants, y=loss_vals, marker_color=["#ff3c5a" if l>t else "#00ff88" for l,t in zip(loss_vals, threshold_vals)], opacity=0.8))
        fig.add_trace(go.Scatter(name="SLA Threshold", x=merchants, y=threshold_vals, mode="markers+lines", marker=dict(color="#ffaa00", size=8, symbol="diamond"), line=dict(color="#ffaa00", dash="dot")))
        fig.update_layout(**PLOTLY_LAYOUT, height=280, yaxis_title="₹ Amount")
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# TAB 4 — QUARANTINE
# ══════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown('<div class="section-header">Quarantine Root Cause Breakdown</div>', unsafe_allow_html=True)

    if not qdf.empty:
        qc1, qc2 = st.columns([1, 2])

        with qc1:
            # Pie chart by reason
            if "reason" in qdf.columns:
                reason_counts = qdf["reason"].value_counts()
                fig_pie = px.pie(
                    values=reason_counts.values,
                    names=reason_counts.index,
                    color_discrete_sequence=["#ff3c5a", "#ffaa00", "#b97aff", "#00e5ff", "#00ff88"],
                    hole=0.55,
                )
                fig_pie.update_layout(
                    **PLOTLY_LAYOUT,
                    height=300,
                    showlegend=True,
                    annotations=[dict(text=f"<b>{len(qdf)}</b><br><span style='font-size:10px'>records</span>", x=0.5, y=0.5, showarrow=False, font=dict(color="#c8daf0", size=14))]
                )
                fig_pie.update_traces(textfont=dict(family="JetBrains Mono", size=10))
                st.plotly_chart(fig_pie, use_container_width=True)

        with qc2:
            # Reason filter
            reasons = ["All"] + (list(qdf["reason"].unique()) if "reason" in qdf.columns else [])
            sel_reason = st.selectbox("Filter by Reason", reasons)

            filtered_q = qdf if sel_reason == "All" else qdf[qdf["reason"] == sel_reason]

            # Stats for selected reason
            if sel_reason != "All":
                st.markdown(f"""
                <div class="sigma-card">
                    <div class="kpi-label">Suggested Fix · {sel_reason}</div>
                    <div style="font-family:var(--mono);font-size:0.7rem;color:#00e5ff;margin-top:0.5rem;line-height:1.8;">
                    {"→ Check upstream data generator — transaction_id is not being populated" if "null" in sel_reason
                     else "→ Validate schema against data contract before COPY INTO" if "schema" in sel_reason
                     else "→ Add transaction_id as deduplication key in Snowflake MERGE statement" if "duplicate" in sel_reason
                     else "→ Add amount validation: amount > 0 required" if "amount" in sel_reason
                     else "→ Investigate source system for this error pattern"}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div class="section-header">Quarantine Records</div>', unsafe_allow_html=True)
            display_cols = [c for c in filtered_q.columns if not c.startswith("_")]
            st.dataframe(
                filtered_q[display_cols].head(50),
                use_container_width=True,
                height=300,
            )

        # Quarantine over time
        if "_ts" in qdf.columns:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">Quarantine Events Over Time</div>', unsafe_allow_html=True)
            qdf["_ts_str"] = pd.to_datetime(qdf["_ts"]).dt.strftime("%H:%M")
            ts_counts = qdf.groupby("_ts_str").size().reset_index(name="count")
            fig_q = px.bar(ts_counts, x="_ts_str", y="count",
                           color_discrete_sequence=["#ffaa00"])
            fig_q.update_layout(**PLOTLY_LAYOUT, height=220, xaxis_title="Time", yaxis_title="Records")
            st.plotly_chart(fig_q, use_container_width=True)
    else:
        st.info("No quarantine records found.")


# ══════════════════════════════════════════════════════════════
# TAB 5 — TOOL EXECUTION AUDIT
# ══════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="section-header">Tool Execution Audit Trail — Last Incident</div>', unsafe_allow_html=True)

    tools_data = get_demo_tools()
    tool_types = ["All"] + list({t["Tool"].split("_")[0] for t in tools_data})
    tc1, tc2 = st.columns([2, 4])
    with tc1:
        type_filter = st.selectbox("Filter by Service", tool_types)
    with tc2:
        search_tool = st.text_input("Search tools / parameters / results", placeholder="e.g. cloudwatch, snowflake, kinesis…")

    filtered_tools = tools_data
    if type_filter != "All":
        filtered_tools = [t for t in filtered_tools if t["Tool"].startswith(type_filter)]
    if search_tool:
        q = search_tool.lower()
        filtered_tools = [t for t in filtered_tools if q in t["Tool"].lower() or q in t["Parameters"].lower() or q in t["Result"].lower()]

    # Header
    h = st.columns([2, 2.5, 2.5, 1, 0.8])
    for col, label in zip(h, ["Tool", "Parameters", "Result", "Time (ms)", "Status"]):
        col.markdown(f"<div style='font-family:var(--mono);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;color:#4a6080;padding:0.3rem 0;'>{label}</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:1px;background:#1e3050;'></div>", unsafe_allow_html=True)

    for i, t in enumerate(filtered_tools):
        row = st.columns([2, 2.5, 2.5, 1, 0.8])
        bg = "rgba(13,24,41,0.5)" if i % 2 == 0 else "transparent"
        with row[0]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.68rem;color:#00e5ff;'>{t['Tool']}</span>", unsafe_allow_html=True)
        with row[1]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.65rem;color:#6b85a0;'>{t['Parameters']}</span>", unsafe_allow_html=True)
        with row[2]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.65rem;color:#c8daf0;'>{t['Result']}</span>", unsafe_allow_html=True)
        with row[3]:
            color = "#ff3c5a" if t["Time (ms)"] > 2000 else "#ffaa00" if t["Time (ms)"] > 800 else "#00ff88"
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.68rem;color:{color};'>{t['Time (ms)']}ms</span>", unsafe_allow_html=True)
        with row[4]:
            badge = '<span class="badge badge-ok">OK</span>' if t["Status"] == "OK" else '<span class="badge badge-breach">FAIL</span>'
            st.markdown(badge, unsafe_allow_html=True)
        st.markdown("<div style='height:1px;background:#132035;'></div>", unsafe_allow_html=True)

    # Summary stats
    st.markdown("<br>", unsafe_allow_html=True)
    total_ms = sum(t["Time (ms)"] for t in tools_data)
    avg_ms = total_ms // len(tools_data)
    slowest = max(tools_data, key=lambda x: x["Time (ms)"])
    st.markdown(f"""
    <div class="sigma-card" style="display:flex;gap:3rem;">
        <div>
            <div class="kpi-label">Total Tool Calls</div>
            <div style="font-family:var(--mono);font-size:1.1rem;font-weight:700;color:#00e5ff;">{len(tools_data)}</div>
        </div>
        <div>
            <div class="kpi-label">Total Time</div>
            <div style="font-family:var(--mono);font-size:1.1rem;font-weight:700;color:#c8daf0;">{total_ms:,}ms</div>
        </div>
        <div>
            <div class="kpi-label">Avg per Call</div>
            <div style="font-family:var(--mono);font-size:1.1rem;font-weight:700;color:#c8daf0;">{avg_ms}ms</div>
        </div>
        <div>
            <div class="kpi-label">Slowest Call</div>
            <div style="font-family:var(--mono);font-size:1.1rem;font-weight:700;color:#ffaa00;">{slowest['Tool']} ({slowest['Time (ms)']}ms)</div>
        </div>
        <div>
            <div class="kpi-label">Success Rate</div>
            <div style="font-family:var(--mono);font-size:1.1rem;font-weight:700;color:#00ff88;">100%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# TAB 6 — SNOWFLAKE LOAD SUMMARY
# ══════════════════════════════════════════════════════════════
with tabs[5]:
    st.markdown('<div class="section-header">Snowflake Load Summary</div>', unsafe_allow_html=True)

    sf = load_snowflake_metrics()
    recovered = sf.get("recovered", 824)
    quarantined = sf.get("quarantined", 23)
    total_today = sf.get("total_rows", 40823)
    gmv_today = sf.get("gmv", 161251.85)

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">Rows Loaded Today</div>
            <div class="kpi-value success">{total_today:,}</div>
            <div class="kpi-sub">post-recovery</div>
        </div>""", unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">Recovered</div>
            <div class="kpi-value success">+{recovered:,}</div>
            <div class="kpi-sub">Kinesis replay</div>
        </div>""", unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">Quarantined</div>
            <div class="kpi-value warn">{quarantined}</div>
            <div class="kpi-sub">null PKs</div>
        </div>""", unsafe_allow_html=True)
    with s4:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">GMV Restored</div>
            <div class="kpi-value success">₹4,69,890</div>
            <div class="kpi-sub">of ₹4,72,340 lost</div>
        </div>""", unsafe_allow_html=True)

    # Load rate bar
    st.markdown("<br>", unsafe_allow_html=True)
    load_success_pct = round(recovered / (recovered + quarantined) * 100, 1)
    st.markdown(f"""
    <div class="sigma-card">
        <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
            <span style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;">Recovery Load Rate</span>
            <span style="font-family:var(--mono);font-size:0.68rem;color:#00ff88;">{load_success_pct}%</span>
        </div>
        <div class="progress-bar-outer">
            <div class="progress-bar-inner" style="width:{load_success_pct}%;background:linear-gradient(90deg,#00ff88,#00e5ff);"></div>
        </div>
        <div style="font-family:var(--mono);font-size:0.62rem;color:#4a6080;margin-top:0.4rem;">
            {recovered} loaded · {quarantined} quarantined · 0 rejected
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Historical chart
    history = sf.get("history", [])
    if history:
        st.markdown('<div class="section-header">7-Day Load History</div>', unsafe_allow_html=True)
        hist_df = pd.DataFrame(history)
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Bar(
            x=hist_df["date"], y=hist_df["rows"],
            name="Rows Loaded",
            marker_color=["#ff3c5a" if r < 50000 else "#00ff88" for r in hist_df["rows"]],
            opacity=0.8,
        ))
        fig_hist.add_trace(go.Scatter(
            x=hist_df["date"], y=hist_df["gmv"],
            name="GMV (₹)",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color="#00e5ff", width=2),
            marker=dict(size=5),
        ))
        fig_hist.update_layout(**PLOTLY_LAYOUT)

        fig_hist.update_layout(
            yaxis=dict(title="Count"), # (Match this to whatever you had in your original file)
            yaxis2=dict(title="GMV (₹)", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)")
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # Data quality metrics
    st.markdown('<div class="section-header">Data Quality Metrics</div>', unsafe_allow_html=True)
    quality_data = [
        {"Field": "transaction_id", "Null %": 2.7, "Schema OK": True,  "Note": "23 null PKs quarantined"},
        {"Field": "merchant_name",  "Null %": 0.0, "Schema OK": True,  "Note": "Post-fix: mapped from merchant_nm"},
        {"Field": "amount",         "Null %": 0.0, "Schema OK": True,  "Note": "All positive, 1 zero quarantined"},
        {"Field": "transaction_date","Null %": 0.0, "Schema OK": True, "Note": "Post-fix: DD-MM → YYYY-MM-DD"},
        {"Field": "merchant_nm",    "Null %": 0.0, "Schema OK": False, "Note": "⚠ v2 field name — caused failure"},
    ]
    qh = st.columns([1.5, 1, 1, 2.5])
    for col, label in zip(qh, ["Field", "Null %", "Schema", "Note"]):
        col.markdown(f"<div style='font-family:var(--mono);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;color:#4a6080;'>{label}</div>", unsafe_allow_html=True)
    for q in quality_data:
        qr = st.columns([1.5, 1, 1, 2.5])
        with qr[0]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.7rem;color:#c8daf0;'>{q['Field']}</span>", unsafe_allow_html=True)
        with qr[1]:
            color = "#ff3c5a" if q["Null %"] > 2 else "#ffaa00" if q["Null %"] > 0 else "#00ff88"
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.7rem;color:{color};'>{q['Null %']}%</span>", unsafe_allow_html=True)
        with qr[2]:
            badge = '<span class="badge badge-ok">✓</span>' if q["Schema OK"] else '<span class="badge badge-breach">✗</span>'
            st.markdown(badge, unsafe_allow_html=True)
        with qr[3]:
            st.markdown(f"<span style='font-family:var(--mono);font-size:0.65rem;color:#6b85a0;'>{q['Note']}</span>", unsafe_allow_html=True)
        st.markdown("<div style='height:1px;background:#132035;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# TAB 7 — ALARM MANAGEMENT
# ══════════════════════════════════════════════════════════════
with tabs[6]:
    st.markdown('<div class="section-header">CloudWatch Alarm Management</div>', unsafe_allow_html=True)

    alarms = load_cloudwatch_alarms()
    ok_count_a   = sum(1 for a in alarms if a["state"] == "OK")
    alarm_count_a = sum(1 for a in alarms if a["state"] == "ALARM")
    insuf_count_a = sum(1 for a in alarms if a["state"] == "INSUFFICIENT_DATA")

    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">OK</div>
            <div class="kpi-value success">{ok_count_a}</div>
        </div>""", unsafe_allow_html=True)
    with ac2:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">ALARM</div>
            <div class="kpi-value danger">{alarm_count_a}</div>
        </div>""", unsafe_allow_html=True)
    with ac3:
        st.markdown(f"""
        <div class="kpi-tile">
            <div class="kpi-label">Insufficient Data</div>
            <div class="kpi-value warn">{insuf_count_a}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    for alarm in alarms:
        state_badge = (
            '<span class="badge badge-ok">✓ OK</span>' if alarm["state"] == "OK"
            else '<span class="badge badge-alarm">⚠ ALARM</span>' if alarm["state"] == "ALARM"
            else '<span class="badge badge-warn">? INSUFFICIENT</span>'
        )
        updated = alarm["updated"]
        if hasattr(updated, "strftime"):
            updated = updated.strftime("%Y-%m-%d %H:%M UTC")

        st.markdown(f"""
        <div class="sigma-card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div style="font-family:var(--mono);font-size:0.82rem;font-weight:700;
                                color:#00e5ff;margin-bottom:0.4rem;">{alarm['name']}</div>
                    <div style="font-family:var(--mono);font-size:0.65rem;color:#6b85a0;
                                margin-bottom:0.6rem;">{alarm.get('description','')}</div>
                    <div style="display:flex;gap:1.5rem;">
                        <div>
                            <div class="kpi-label">Metric</div>
                            <div style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;">{alarm['metric']}</div>
                        </div>
                        <div>
                            <div class="kpi-label">Threshold</div>
                            <div style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;">{alarm['comparison']} {alarm['threshold']}</div>
                        </div>
                        <div>
                            <div class="kpi-label">Namespace</div>
                            <div style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;">{alarm.get('namespace','—')}</div>
                        </div>
                        <div>
                            <div class="kpi-label">Last Updated</div>
                            <div style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;">{updated}</div>
                        </div>
                    </div>
                </div>
                <div>{state_badge}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    try:
        region = st.secrets["aws"]["region"]
        st.markdown(f"""
        <div style="margin-top:1rem;font-family:var(--mono);font-size:0.68rem;color:#4a6080;">
            → <a href="https://console.aws.amazon.com/cloudwatch/home?region={region}#alarmsV2:?search=sigma-"
                  target="_blank" style="color:#00e5ff;text-decoration:none;">
                Open in AWS CloudWatch Console ↗
            </a>
        </div>
        """, unsafe_allow_html=True)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# TAB 8 — AGENT COLLABORATION GRAPH
# ══════════════════════════════════════════════════════════════
with tabs[7]:
    st.markdown('<div class="section-header">Agent Collaboration DAG</div>', unsafe_allow_html=True)

    # Build network graph with plotly
    nodes = {
        "SUPERVISOR":      (0.5, 0.85),
        "FORENSICS":       (0.1, 0.55),
        "IMPACT":          (0.35, 0.55),
        "RECOVERY":        (0.1, 0.2),
        "ROLLBACK":        (0.35, 0.2),
        "HARDENING":       (0.65, 0.2),
        "INCIDENT REPORT": (0.9, 0.2),
        "MCP SERVER":      (0.75, 0.55),
        "KNOWLEDGE BASE":  (0.9, 0.55),
    }
    colors = {
        "SUPERVISOR":      "#00e5ff",
        "FORENSICS":       "#b97aff",
        "IMPACT":          "#ffaa00",
        "RECOVERY":        "#00ff88",
        "ROLLBACK":        "#ff6b35",
        "HARDENING":       "#ff3c5a",
        "INCIDENT REPORT": "#4fc3f7",
        "MCP SERVER":      "#4a6080",
        "KNOWLEDGE BASE":  "#4a6080",
    }
    edges = [
        ("SUPERVISOR", "FORENSICS"),
        ("SUPERVISOR", "IMPACT"),
        ("SUPERVISOR", "RECOVERY"),
        ("SUPERVISOR", "ROLLBACK"),
        ("SUPERVISOR", "HARDENING"),
        ("SUPERVISOR", "INCIDENT REPORT"),
        ("SUPERVISOR", "MCP SERVER"),
        ("SUPERVISOR", "KNOWLEDGE BASE"),
        ("FORENSICS",  "MCP SERVER"),
        ("IMPACT",     "KNOWLEDGE BASE"),
        ("RECOVERY",   "MCP SERVER"),
        ("HARDENING",  "MCP SERVER"),
    ]

    fig_dag = go.Figure()

    # Draw edges
    for src, dst in edges:
        x0, y0 = nodes[src]
        x1, y1 = nodes[dst]
        is_main = dst in ("FORENSICS", "IMPACT", "RECOVERY", "ROLLBACK", "HARDENING", "INCIDENT REPORT")
        fig_dag.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(color="#1e3050" if not is_main else colors.get(src, "#1e3050"),
                      width=2 if is_main else 1,
                      dash="dot" if not is_main else "solid"),
            showlegend=False, hoverinfo="skip",
        ))

    # Draw nodes
    for name, (x, y) in nodes.items():
        is_support = name in ("MCP SERVER", "KNOWLEDGE BASE")
        fig_dag.add_trace(go.Scatter(
            x=[x], y=[y],
            mode="markers+text",
            marker=dict(
                size=45 if name == "SUPERVISOR" else 30 if not is_support else 22,
                color=colors.get(name, "#4a6080"),
                opacity=0.2 if is_support else 0.85,
                line=dict(color=colors.get(name, "#4a6080"), width=2),
            ),
            text=[name.replace(" ", "<br>")],
            textposition="middle center",
            textfont=dict(family="JetBrains Mono", size=7, color="#020811" if not is_support else "#6b85a0"),
            name=name,
            hovertemplate=f"<b>{name}</b><extra></extra>",
        ))

    fig_dag.update_layout(
        **PLOTLY_LAYOUT,
        height=480,
        showlegend=False,
        xaxis=dict(visible=False, range=[-0.05, 1.05]),
        yaxis=dict(visible=False, range=[0.05, 1.0]),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_dag, use_container_width=True)

    # Legend
    st.markdown("""
    <div style="display:flex;flex-wrap:wrap;gap:1rem;font-family:var(--mono);font-size:0.65rem;color:#6b85a0;margin-top:-0.5rem;">
        <span><span style="color:#00e5ff;">●</span> Supervisor — orchestrates</span>
        <span><span style="color:#b97aff;">●</span> Forensics — root cause</span>
        <span><span style="color:#ffaa00;">●</span> Impact — business effect</span>
        <span><span style="color:#00ff88;">●</span> Recovery — Kinesis replay</span>
        <span><span style="color:#ff6b35;">●</span> Rollback — Lambda version</span>
        <span><span style="color:#ff3c5a;">●</span> Hardening — alarms</span>
        <span><span style="color:#4fc3f7;">●</span> Incident Report — S3 post-mortem</span>
        <span><span style="color:#4a6080;">●</span> MCP/KB — shared infrastructure</span>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# TAB 9 — SEARCH & DRILL-DOWN
# ══════════════════════════════════════════════════════════════
with tabs[8]:
    st.markdown('<div class="section-header">Full-Text Search — Incidents · Quarantine · Tools</div>', unsafe_allow_html=True)

    sc1, sc2, sc3 = st.columns([3, 1.5, 1.5])
    with sc1:
        search_q = st.text_input("", placeholder="Search across all incident reports, quarantine reasons, tool results…", label_visibility="collapsed")
    with sc2:
        scope = st.selectbox("Scope", ["All", "Incident Reports", "Quarantine", "Tool Audit"])
    with sc3:
        date_filter = st.date_input("Since date", value=datetime.now().date() - timedelta(days=30))

    if search_q:
        results = []
        q_lower = search_q.lower()

        if scope in ("All", "Incident Reports"):
            for r in reports:
                mod_date = r["last_modified"].date() if hasattr(r["last_modified"], "date") else datetime.now().date()
                if mod_date >= date_filter and q_lower in r["content"].lower():
                    lines = [l for l in r["content"].splitlines() if q_lower in l.lower()]
                    for line in lines[:3]:
                        results.append({"Source": "Report", "File": r["filename"], "Match": line.strip()[:120], "Date": str(mod_date)})

        if scope in ("All", "Quarantine") and not qdf.empty:
            for _, row in qdf.iterrows():
                row_str = " ".join(str(v) for v in row.values).lower()
                if q_lower in row_str:
                    results.append({"Source": "Quarantine", "File": row.get("_s3_key", "quarantine"), "Match": str(dict(row))[:120], "Date": str(row.get("_ts", ""))[:10]})

        if scope in ("All", "Tool Audit"):
            for t in get_demo_tools():
                if q_lower in t["Tool"].lower() or q_lower in t["Parameters"].lower() or q_lower in t["Result"].lower():
                    results.append({"Source": "Tool", "File": t["Tool"], "Match": f"Params: {t['Parameters']} → {t['Result']}", "Date": "2026-06-04"})

        if results:
            st.markdown(f"<div style='font-family:var(--mono);font-size:0.7rem;color:#00ff88;margin-bottom:1rem;'>→ {len(results)} result{'s' if len(results)!=1 else ''} for \"{search_q}\"</div>", unsafe_allow_html=True)
            for res in results[:30]:
                src_color = {"Report": "#00e5ff", "Quarantine": "#ffaa00", "Tool": "#b97aff"}.get(res["Source"], "#c8daf0")
                st.markdown(f"""
                <div style="padding:0.6rem 0;border-bottom:1px solid #132035;">
                    <div style="display:flex;gap:1rem;align-items:center;margin-bottom:0.25rem;">
                        <span class="badge" style="background:rgba(0,0,0,0.3);color:{src_color};border:1px solid {src_color}33;">{res['Source']}</span>
                        <span style="font-family:var(--mono);font-size:0.65rem;color:#6b85a0;">{res['File']}</span>
                        <span style="font-family:var(--mono);font-size:0.62rem;color:#4a6080;">{res['Date']}</span>
                    </div>
                    <div style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;line-height:1.6;">
                        {res['Match']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-family:var(--mono);font-size:0.7rem;color:#4a6080;'>No results for \"{search_q}\"</div>", unsafe_allow_html=True)
    else:
        # Default: show recent activity summary
        st.markdown('<div class="section-header">Recent Activity</div>', unsafe_allow_html=True)
        activity = [
            ("2026-06-04 13:31", "RECOVERY", "824 records replayed from Kinesis, GMV ₹4,69,890 restored", "#00ff88"),
            ("2026-06-04 13:31", "HARDENING", "3 CloudWatch alarms created: snowflake-zero-load, lambda-version-change, row-divergence", "#ff3c5a"),
            ("2026-06-04 13:31", "FORENSICS", "Root cause identified: Lambda v2 schema mismatch at 02:11 UTC", "#b97aff"),
            ("2026-06-04 09:03", "SUPERVISOR", "Incident triggered: 80,000 records missing from dashboard", "#00e5ff"),
            ("2026-05-20 06:46", "RECOVERY", "299 records replayed, Kinesis iterator refresh added to runbook", "#00ff88"),
        ]
        for ts, agent, event, color in activity:
            st.markdown(f"""
            <div style="display:flex;gap:1rem;padding:0.55rem 0;border-bottom:1px solid #132035;align-items:flex-start;">
                <span style="font-family:var(--mono);font-size:0.62rem;color:#4a6080;min-width:130px;">{ts}</span>
                <span style="font-family:var(--mono);font-size:0.62rem;font-weight:700;color:{color};min-width:120px;">{agent}</span>
                <span style="font-family:var(--mono);font-size:0.68rem;color:#c8daf0;">{event}</span>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# AUTO-REFRESH
# ─────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(60)
    st.rerun()