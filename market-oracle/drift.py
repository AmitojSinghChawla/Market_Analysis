import pandas as pd

from db import get_connected


def establish_connection():
    try:
        conn=get_connected()
        return conn
    except Exception as e:
        print(e)

REFERENCE_WINDOW= 30

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

def get_data(conn) -> pd.DataFrame:

    cursor = conn.cursor()

    query="SELECT date,daily_return,ma_7,ma_21, ma_ratio, rsi,volatility_7,volume_change,macd,stochastic FROM features ORDER BY date"

    df=pd.read_sql(query,conn)

    return df


def separate_data(df) -> pd.DataFrame:

    df['date']=pd.to_datetime(df['date'])




    return df
