import psycopg2
from psycopg2.extras import execute_values
from config import DB_CONFIG


def get_connected():
    """Connect to the PostgreSQL database server on cloud using the neon database service
    earlier we were using local postgresql database."""

    config = DB_CONFIG.copy()
    config["sslmode"] = "require"
    return psycopg2.connect(**config)


def create_tables():
    """Create the tables in the database"""
    conn = get_connected()
    cursor = conn.cursor()

    # Creating Prices Table

    cursor.execute("""
         CREATE TABLE IF NOT EXISTS prices(
         id             SERIAL PRIMARY KEY,
         ticker         VARCHAR NOT NULL,
         date           DATE NOT NULL,
         open           NUMERIC(18,6),
         high           NUMERIC(18,6),
         low            NUMERIC(18,6),
         close          NUMERIC(18,6),
         volume         NUMERIC(18,6),
         created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         UNIQUE(ticker, date)
         );
    """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS news (
                   id               SERIAL PRIMARY KEY,
                   ticker           VARCHAR NOT NULL,
                   published        TIMESTAMP NOT NULL,
                   title            TEXT NOT NULL,
                   source           VARCHAR,
                   url              TEXT,
                   created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   UNIQUE(ticker, title)
                   );
                   """)

    cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_price_ticker_date
                    ON prices(ticker, date) """)

    cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_ticker_published
                ON news(ticker, published) """)

    conn.commit()
    cursor.close()
    conn.close()
    print(f"TABLES CREATED")


def get_latest_date(table, ticker):
    conn = get_connected()
    cursor = conn.cursor()

    date_col = "date" if table == "prices" else "published"
    cursor.execute(f"SELECT MAX({date_col}) FROM {table} WHERE ticker = %s", (ticker,))

    result = cursor.fetchone()

    cursor.close()
    conn.close()
    return result[0]


def save_features(df):
    conn = get_connected()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id              SERIAL PRIMARY KEY,
            ticker          VARCHAR NOT NULL,
            date            DATE NOT NULL,
            daily_return    NUMERIC,
            ma_7            NUMERIC,
            ma_21           NUMERIC,
            ma_ratio        NUMERIC,
            rsi             NUMERIC,
            volatility_7    NUMERIC,
            volume_change   NUMERIC,
            sentiment_score NUMERIC,
            macd            NUMERIC,
            stochastic      NUMERIC,
            target          INTEGER,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, date)
        );
    """)

    cols = ["ticker", "date", "daily_return", "ma_7", "ma_21", "ma_ratio",
            "rsi", "volatility_7", "volume_change", "sentiment_score",
            "macd", "stochastic", "target"]

    rows = [tuple(row) for row in df[cols].itertuples(index=False)]
    execute_values(cursor, f"""
        INSERT INTO features ({", ".join(cols)})
        VALUES %s
        ON CONFLICT (ticker, date) DO NOTHING
    """, rows)

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Saved {len(rows)} feature rows to DB")


if __name__ == "__main__":
    create_tables()
