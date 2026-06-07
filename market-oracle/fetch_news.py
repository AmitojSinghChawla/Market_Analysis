import requests
from datetime import datetime, timedelta
from db import get_connected, get_latest_date
from config import *


def start_date(ticker, table):
    date = get_latest_date(table, ticker)

    if date is None:
        today = datetime.today()
        two_years_ago = today - timedelta(days=30)
        return two_years_ago.strftime("%Y-%m-%d")
    else:
        date = date + timedelta(days=1)
        return date.strftime("%Y-%m-%d")


def fetch_news(ticker, table, cursor):

    date = start_date(ticker, table)

    params = {
        "q": NEWS_SEARCH_TERMS[ticker],
        "from": date,
        "language": "en",
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
    }

    try:
        data = requests.get(NEWS_API_URL, params=params).json()
    except Exception as e:
        print(f"API CALL ERROR FOR TICKER {ticker}, {e}")
        return

    for article in data["articles"]:
        try:
            title = article["title"]
            published = article["publishedAt"]
            source = article["source"]["name"]
            url = article["url"]

            cursor.execute(
                "INSERT INTO news ( ticker, published, title, source, url) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (
                    ticker,
                    published,
                    title,
                    source,
                    url,
                ),
            )
            title = article["title"]
        except Exception as e:
            print(f"SKIPPING ARTICLE {ticker}, {e}")
            continue


if __name__ == "__main__":
    conn = get_connected()
    cur = conn.cursor()

    for ticker in ALL_TICKERS:
        print(f"Fetching {ticker}...")
        fetch_news(ticker, "prices", cur)

    conn.commit()
    print("All news saved.")
    cur.close()
    conn.close()
