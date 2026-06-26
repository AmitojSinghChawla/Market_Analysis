"""
drift_detect.py — Data Drift Detection for MarketPulse
=======================================================
Compares OLD feature distributions (reference) against RECENT data (current)
using Population Stability Index (PSI) via Evidently AI.

WHY PSI?
- Finance industry standard for distribution shift
- Easy to interpret: <0.1 = no drift, 0.1-0.25 = moderate, >0.25 = significant
- Works well with our ~5800 rows

WHAT WE MONITOR (9 features):
- daily_return, ma_7, ma_21, ma_ratio, rsi, volatility_7,
  volume_change, macd, stochastic

WHAT WE EXCLUDE:
- sentiment_score: 98% zeros, any drift test on it is noise
- target: label, not an input feature

REFERENCE vs CURRENT:
- Reference = features older than 30 days (the "normal")
- Current = last 30 days (what the model sees now)
- If current differs from reference, model is in unfamiliar territory

OUTPUT:
- drift_report.html — interactive report with per-feature PSI scores
"""

import pandas as pd
from datetime import datetime, timedelta

from evidently import Report
from evidently.presets import DataDriftPreset

# Import from your existing project files
from db import get_connected

# ─── CONFIG ────────────────────────────────────────────────────────────

# The 9 features we monitor — sentiment_score excluded (98% zeros)
DRIFT_FEATURES = [
    "daily_return",
    "ma_7",
    "ma_21",
    "ma_ratio",
    "rsi",
    "volatility_7",
    "volume_change",
    "macd",
    "stochastic",
]

CURRENT_WINDOW_DAYS = 30


# ─── DATABASE ──────────────────────────────────────────────────────────

def get_features() -> pd.DataFrame:
    """Pull all rows from the features table using existing db.py connection."""
    conn = get_connected()
    query = """
        SELECT ticker, date, daily_return, ma_7, ma_21, ma_ratio,
               rsi, volatility_7, volume_change, macd, stochastic
        FROM features
        ORDER BY date
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# ─── DRIFT DETECTION ──────────────────────────────────────────────────

def split_reference_current(df: pd.DataFrame):
    """
    Reference = everything older than 30 days
    Current = last 30 days

    Catches regime change: if recent market behavior differs
    from the historical norm the model learned from.
    """
    cutoff_date = datetime.now().date() - timedelta(days=CURRENT_WINDOW_DAYS)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    reference = df[df["date"] < cutoff_date]
    current = df[df["date"] >= cutoff_date]

    print(f"Reference: {len(reference)} rows (before {cutoff_date})")
    print(f"Current:   {len(current)} rows (after {cutoff_date})")

    if len(reference) == 0:
        raise ValueError("No reference data found.")
    if len(current) == 0:
        raise ValueError("No current data found. Has fresh data been fetched?")

    return reference, current


def run_drift_report(reference: pd.DataFrame, current: pd.DataFrame) -> Report:
    """
    Run PSI drift detection on 9 features.

    IMPORTANT: .run() takes CURRENT first, REFERENCE second.
    Opposite of what you'd expect. Getting it backwards
    silently inverts drift interpretation.
    """
    ref_features = reference[DRIFT_FEATURES].dropna()
    cur_features = current[DRIFT_FEATURES].dropna()

    print(f"After dropping NaNs — Reference: {len(ref_features)}, Current: {len(cur_features)}")

    # method="psi" = Population Stability Index
    report = Report([DataDriftPreset(method="psi")])

    # CURRENT FIRST, then reference
    report.run(cur_features, ref_features)

    return report


# ─── MAIN ──────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("MarketPulse Drift Detection")
    print("=" * 60)

    print("\n[1/3] Fetching features from database...")
    df = get_features()
    print(f"Total rows: {len(df)}")

    print("\n[2/3] Splitting reference vs current...")
    reference, current = split_reference_current(df)

    print("\n[3/3] Running PSI drift detection...")
    report = run_drift_report(reference, current)

    # Save HTML report
    output_path = "drift_report.html"
    report.save_html(output_path)
    print(f"\nReport saved to {output_path}")

    # Print quick summary to console
    result_dict = report.as_dict()
    metrics = result_dict.get("metrics", [])
    if metrics:
        print("\n" + "=" * 60)
        print("DRIFT SUMMARY")
        print("=" * 60)
        for metric in metrics:
            result = metric.get("result", {})
            if "share_of_drifted_columns" in result:
                share = result["share_of_drifted_columns"]
                dataset_drift = result.get("dataset_drift", False)
                print(f"Dataset drift detected: {dataset_drift}")
                print(f"Drifted columns: {share:.1%}")
            if "drift_by_columns" in result:
                print(f"\n{'Feature':<20} {'PSI Score':<12} {'Drift?'}")
                print("-" * 45)
                for col, col_result in result["drift_by_columns"].items():
                    score = col_result.get("drift_score", 0)
                    drifted = col_result.get("drift_detected", False)
                    status = "YES" if drifted else "no"
                    print(f"{col:<20} {score:<12.4f} {status}")


if __name__ == "__main__":
    main()