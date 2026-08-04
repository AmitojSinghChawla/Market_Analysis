# MarketPulse (Market Oracle)

MarketPulse is an end-to-end machine learning pipeline that predicts whether a stock or crypto ticker will close **up or down the next trading day**. It ingests daily price data and financial news, engineers technical + sentiment features, trains an XGBoost classifier, and serves predictions through a FastAPI REST API. The whole pipeline retrains itself automatically every week via GitHub Actions and redeploys to Render.

## How it works

```
 ┌─────────────┐     ┌─────────────┐
 │ fetch_prices│     │ fetch_news  │
 │  (yfinance) │     │ (NewsAPI)   │
 └──────┬──────┘     └──────┬──────┘
        │                   │
        ▼                   ▼
      ┌───────────────────────┐
      │   PostgreSQL (Neon)   │  prices, news, features tables
      └───────────┬───────────┘
                   ▼
      ┌───────────────────────┐
      │      train.py         │  feature engineering + FinBERT
      │  - technical indicators│  sentiment scoring + XGBoost
      │  - sentiment scoring   │  training, tracked in MLflow
      │  - XGBoost training    │
      └───────────┬───────────┘
                   ▼
      ┌───────────────────────┐
      │     models/model.pkl   │
      └───────────┬───────────┘
                   ▼
      ┌───────────────────────┐
      │   FastAPI app (app.py) │  GET /predict?ticker=AAPL
      └───────────────────────┘
```

## Features

- **Data ingestion**
  - `fetch_prices.py` — pulls daily OHLCV data for a configurable list of stocks and crypto tickers via [yfinance](https://pypi.org/project/yfinance/), with incremental backfill (only fetches new dates since the last stored record).
  - `fetch_news.py` — pulls recent headlines per ticker from [NewsAPI](https://newsapi.org/), used later for sentiment scoring.
- **Feature engineering** (`train.py`)
  - Technical indicators: daily return, 7/21-day moving averages, MA ratio, RSI, MACD, stochastic oscillator, 7-day volatility, volume change.
  - News sentiment: headlines are scored with [FinBERT](https://huggingface.co/ProsusAI/finbert) (`ProsusAI/finbert`) and aggregated into a daily sentiment score per ticker.
  - Binary target: whether next day's close is higher than today's close.
- **Model training**
  - `XGBoostClassifier` trained with a chronological train/test split (80/20 by date to avoid lookahead bias) and class-imbalance handling via `scale_pos_weight`.
  - Runs and metrics (accuracy, precision, recall, F1) are tracked with [MLflow](https://mlflow.org/) (`mlflow.db`).
  - The trained model is serialized to `market-oracle/models/model.pkl`.
- **Serving**
  - `app.py` — a FastAPI service that loads the model once at startup and exposes:
    - `GET /predict?ticker=<TICKER>` — returns predicted direction (`up`/`down`), confidence, and the prediction date.
    - `GET /` — health check.
- **Storage** — PostgreSQL (hosted on [Neon](https://neon.tech/)) with three tables: `prices`, `news`, and `features`, each keyed to avoid duplicate inserts.
- **Automation** — a weekly GitHub Actions workflow (`.github/workflows/weekly_app_update.yaml`) fetches the latest prices/news, retrains the model, commits the updated model artifact, and triggers a redeploy on Render.
- **Deployment** — containerized with Docker (`market-oracle/Dockerfile`) and deployed on [Render](https://render.com/) (`render.yaml`) as a free-tier web service.

## Tracked assets

| Type   | Tickers |
|--------|---------|
| Stocks | AAPL, MSFT, GOOGL, TSLA, JPM, JNJ |
| Crypto | BTC-USD, ETH-USD, SOL-USD, BNB-USD |

Configurable in `market-oracle/config.py`.

## Project structure

```
Market_Analysis/
├── render.yaml                          # Render deployment config
├── .github/workflows/
│   └── weekly_app_update.yaml           # weekly fetch → train → deploy pipeline
└── market-oracle/
    ├── app.py                           # FastAPI prediction service
    ├── config.py                        # tickers, DB config, news API config
    ├── db.py                            # PostgreSQL connection + schema + upserts
    ├── fetch_prices.py                  # price ingestion (yfinance)
    ├── fetch_news.py                    # news ingestion (NewsAPI)
    ├── train.py                         # feature engineering + model training
    ├── drift.py                         # (reserved for data/model drift checks)
    ├── feature_engineering.ipynb        # exploratory notebook
    ├── models/model.pkl                 # latest trained model artifact
    ├── mlruns/, mlflow.db               # MLflow experiment tracking
    ├── requirements.txt                 # runtime (API) dependencies
    ├── requirements-train.txt           # training pipeline dependencies
    └── Dockerfile
```

## Getting started

### Prerequisites

- Python 3.12
- A PostgreSQL database (e.g. a free [Neon](https://neon.tech/) instance)
- A [NewsAPI](https://newsapi.org/) API key

### Setup

1. Clone the repo and install dependencies:

   ```bash
   git clone https://github.com/amitojsinghchawla/market_analysis.git
   cd market_analysis/market-oracle
   pip install -r requirements-train.txt   # full pipeline: ingestion + training
   # or just: pip install -r requirements.txt   # API serving only
   ```

2. Create a `.env` file in the project root with your credentials:

   ```env
   DB_NAME=market_pulse
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_HOST=your_db_host
   DB_PORT=5432
   NEWS_API_KEY=your_newsapi_key
   ```

3. Create the database tables:

   ```bash
   python db.py
   ```

4. Run the pipeline:

   ```bash
   python fetch_prices.py     # backfill/update price data
   python fetch_news.py       # backfill/update news data
   python train.py            # build features, score sentiment, train model
   ```

5. Serve predictions locally:

   ```bash
   uvicorn app:app --reload
   ```

   Then query:

   ```bash
   curl "http://localhost:8000/predict?ticker=AAPL"
   ```

### Running with Docker

```bash
docker build -t marketpulse -f market-oracle/Dockerfile market-oracle
docker run -p 8000:8000 --env-file .env marketpulse
```

## Deployment & automation

- **Render** hosts the FastAPI service as a Docker web service, defined in `render.yaml`.
- **GitHub Actions** (`weekly_app_update.yaml`) runs every Friday at 23:00 UTC (and can be triggered manually) to:
  1. Fetch the latest prices and news.
  2. Retrain the model on the updated dataset.
  3. Commit the new `model.pkl` back to the repo.
  4. Trigger a Render deploy hook to roll out the freshly trained model.

## Roadmap / Future scope

- **Streamlit front-end** — a user-facing web app (planned to live alongside the FastAPI backend, e.g. under a `dashboard/` or `streamlit_app/` directory) that will let users:
  - Search/select a ticker and view its predicted direction and confidence at a glance.
  - Visualize historical prices, technical indicators, and sentiment trends.
  - Show model performance and recent prediction history over time.
  - Call the existing `/predict` FastAPI endpoint as its backend, keeping the API and UI decoupled.
- **Model monitoring with Evidently AI** — integrate [Evidently AI](https://www.evidentlytoolkit.com/) into the pipeline (building on the currently empty `drift.py` placeholder) to:
  - Detect **data drift** between the features used in training and the features seen in production/inference.
  - Detect **target/concept drift** as market conditions change over time.
  - Track **prediction and model quality drift** (accuracy/precision/recall decay) once ground-truth outcomes are known.
  - Generate drift/quality reports automatically as part of the weekly GitHub Actions retraining run, with alerts/thresholds that can trigger retraining or flag when the model needs review.
- Additional ideas under consideration:
  - Expanding the tracked ticker universe and supporting user-added tickers.
  - Backtesting and portfolio-level simulation of prediction accuracy.
  - Authentication and rate-limiting on the public API.
  - Multi-day / multi-horizon predictions instead of just next-day direction.

## Tech stack

- **Language:** Python 3.12
- **API:** FastAPI, Uvicorn
- **ML:** XGBoost, scikit-learn, FinBERT (Transformers), MLflow
- **Data:** PostgreSQL (Neon), yfinance, NewsAPI
- **Infra:** Docker, Render, GitHub Actions
- **Planned:** Streamlit (UI), Evidently AI (monitoring)

## License

No license file is currently included in this repository.
