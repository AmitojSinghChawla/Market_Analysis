"""this script is for running the fast api back-end which will receive the requests and return

the prediction via tha REST API GET method about weather the given ticker value would go up or

down the next day """

from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
import joblib
import pandas as pd
from db import get_connected


# ── Load models once at startup (not per request) ───────────────
app = FastAPI()
model = joblib.load("models/model.pkl")  # XGBoost model trained in train.py


# ── Feature columns (must match what the model was trained on) ──
FEATURE_COLS = [
    "daily_return",
    "ma_7",
    "ma_21",
    "ma_ratio",
    "rsi",
    "volatility_7",
    "volume_change",
    "sentiment_score",
    "macd",
    "stochastic",
]


def get_latest_features(ticker: str):
    """
    Fetches recent price + news data for a single ticker,
    builds the same features used in training,
    and returns the latest row ready for prediction.
    """
    conn = get_connected()
    try:
        all_features = pd.read_sql(
            "SELECT * FROM features WHERE ticker=%s ORDER BY date DESC LIMIT 1",
            conn,
            params=(ticker,),
        )
    finally:
        conn.close()

    if all_features.empty:
        raise HTTPException(status_code=404, detail=f"No features found for ticker {ticker}")

    req_features = all_features[FEATURE_COLS]
    return req_features



# ── Prediction endpoint ────────────────────────────────────────
@app.get("/predict")
def predict(ticker: str):
    """
    GET /predict?ticker=AAPL
    Returns the model's prediction for tomorrow's price direction.
    """
    latest = get_latest_features(ticker)

    # predict_proba returns [[prob_down, prob_up]] for each row
    # [0] grabs the first (only) row's probabilities
    probability = model.predict_proba(latest)[0]
    confidence = float(probability[1])  # probability of going up

    # Determine direction and report confidence in that direction
    if confidence > 0.5:
        direction = "up"
    else:
        direction = "down"
        confidence = (
            1 - confidence
        )  # flip so confidence is always for the chosen direction

    prediction_date = (datetime.today().date() + timedelta(days=1)).isoformat()

    return {
        "ticker": ticker,
        "direction": direction,
        "confidence": round(confidence, 4),  # round to 4 decimal places
        "prediction_date": prediction_date,
    }


# ── Health check endpoint ──────────────────────────────────────
@app.get("/")
def health():
    """Simple endpoint to verify the API is running."""
    return {"status": "running", "model": "XGBoost v1"}
