import psycopg2
from psycopg2.extras import execute_values
from config import DB_CONFIG


def get_connected():
    """ Connect to the PostgreSQL database server """

    return psycopg2.connect(**DB_CONFIG)


def create_tables():
    """ Create the tables in the database """
    conn = get_connected()
    cursor = conn.cursor()

    #Creating Prices Table

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
                ON news(ticker, published) """
                   )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"TABLES CREATED")


def get_latest_date(table,ticker):
    conn = get_connected()
    cursor = conn.cursor()

    date_col = "date" if table == "prices" else "published"
    cursor.execute(
        f"SELECT MAX({date_col}) FROM {table} WHERE ticker = %s",(ticker,)
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()
    return result[0]


if __name__ == "__main__":
    create_tables()