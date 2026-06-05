import yfinance as yf
from config import ALL_TICKERS, BACKFILL_YEARS
from db import get_latest_date, get_connected
from datetime import datetime, timedelta
import pandas as pd


def start_date(ticker, table):
    date = get_latest_date(table, ticker)

    if date is None:
        today = datetime.today()
        two_years_ago = today - timedelta(days=365 * BACKFILL_YEARS)
        return two_years_ago.strftime("%Y-%m-%d")
    else:
        date = date + timedelta(days=1)
        return date.strftime("%Y-%m-%d")


def latest_prices(ticker, table, cursor):

    date = start_date(ticker, table)

    data = yf.download(
        ticker, start=date, interval="1d", end=datetime.today(), progress=False
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    if data.empty:
        print(f"No new data for {ticker}")
        return
    else:

        for row in data.itertuples():
            cursor.execute(
                "INSERT INTO prices (ticker, date, open, high, low, close, volume) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (ticker, row.Index, row.Open, row.High, row.Low, row.Close, row.Volume),
            )


if __name__ == "__main__":
    conn = get_connected()
    cur = conn.cursor()

    for ticker in ALL_TICKERS:
        print(f"Fetching {ticker}...")
        latest_prices(ticker, "prices", cur)

    conn.commit()
    print("All prices saved.")
    cur.close()
    conn.close()
