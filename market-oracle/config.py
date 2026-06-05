import os
from dotenv import load_dotenv

load_dotenv()

ASSETS = {
    "stocks": ["AAPL", "MSFT", "GOOGL", "TSLA", "JPM", "JNJ"],
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
}
BACKFILL_YEARS = 2

ALL_TICKERS = ASSETS["stocks"] + ASSETS["crypto"]

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "market_pulse"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"


NEWS_SEARCH_TERMS = {
    "AAPL": "Apple stock",
    "MSFT": "Microsoft stock",
    "GOOGL": "Google Alphabet stock",
    "TSLA": "Tesla stock",
    "JPM": "JPMorgan stock",
    "JNJ": "Johnson Johnson stock",
    "BTC-USD": "Bitcoin BTC",
    "ETH-USD": "Ethereum ETH",
    "SOL-USD": "Solana SOL",
    "BNB-USD": "Binance BNB",
}
