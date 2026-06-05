"""this script is for running the fast api back-end which will receive the requests and return

the prediction via tha REST API GET method about weather the given ticker value would go up or

down the next day """

from datetime import datetime, timedelta  # combined into one import
from fastapi import FastAPI, HTTPException
import joblib
import pandas as pd
from db import get_connected  # check: your db.py uses get_connection, not get_connected
from train import build_features, get_sentiment_score


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

    # Step 1: Fetch last 50 days of prices
    # Need enough history to compute 26-day EMA (MACD) and 21-day MA
    prices = pd.read_sql(
        "SELECT * FROM prices WHERE ticker = %s ORDER BY date DESC LIMIT 50",
        conn,
        params=(ticker,),
    )

    if prices.empty:
        conn.close()
        raise HTTPException(status_code=404, detail=f"No price data found for {ticker}")

    # Step 2: Reverse to chronological order (SQL returned newest first)
    prices = prices.sort_values("date")

    # Step 3: Build technical features using the same function from train.py
    # This adds: daily_return, ma_7, ma_21, ma_ratio, rsi,
    #            volatility_7, volume_change, macd, stochastic
    raw_features = build_features(prices)

    # Step 4: Fetch last 7 days of news for this ticker
    ticker_news = pd.read_sql(
        "SELECT * FROM news WHERE ticker = %s AND published >= NOW() - INTERVAL '7 days'",
        conn,
        params=(ticker,),
    )
    conn.close()  # done with DB — close connection

    # Step 5: Score headlines with FinBERT and compute daily sentiment
    if not ticker_news.empty:
        ticker_news["sentiment"] = ticker_news["title"].apply(
            lambda headline: get_sentiment_score(headline)
        )
        ticker_news["date"] = ticker_news["published"].dt.date
        daily_sentiment = ticker_news.groupby("date")["sentiment"].mean().reset_index()
        daily_sentiment.columns = ["date", "sentiment_score"]
    else:
        # No news found — create empty DataFrame so merge still works
        daily_sentiment = pd.DataFrame(columns=["date", "sentiment_score"])

    # Step 6: Merge sentiment into features
    raw_features["date"] = pd.to_datetime(raw_features["date"]).dt.date
    features = raw_features.merge(daily_sentiment, on="date", how="left")
    features["sentiment_score"] = features["sentiment_score"].fillna(
        0
    )  # no news = neutral

    # Step 7: Return only the latest row's features as a DataFrame
    latest = features[FEATURE_COLS].iloc[-1:]
    return latest




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
