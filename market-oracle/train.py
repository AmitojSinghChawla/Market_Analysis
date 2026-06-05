import pandas as pd


def load_data():

    from db import get_connected

    conn = get_connected()

    prices = pd.read_sql("SELECT * FROM prices ORDER BY ticker,date", conn)
    news = pd.read_sql("SELECT * FROM news ORDER BY ticker, published", conn)
    conn.close()
    return prices, news


def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    return ema12 - ema26


def calculate_stochastic(group):
    from ta.momentum import StochasticOscillator

    return StochasticOscillator(
        high=group["high"], low=group["low"], close=group["close"], window=14
    ).stoch()


def build_features(prices):
    prices["daily_return"] = prices.groupby("ticker")[
        "close"
    ].pct_change()  # returns us the difference in the closing price from last day and today
    prices["ma_7"] = prices.groupby("ticker")["close"].transform(
        lambda x: x.rolling(7).mean()
    )
    prices["ma_21"] = prices.groupby("ticker")["close"].transform(
        lambda x: x.rolling(21).mean()
    )
    prices["ma_ratio"] = prices["ma_7"] / prices["ma_21"]
    prices["volatility_7"] = prices.groupby("ticker")["daily_return"].transform(
        lambda x: x.rolling(7).std()
    )
    prices["volume_change"] = prices.groupby("ticker")["volume"].pct_change()
    prices["rsi"] = prices.groupby("ticker")["close"].transform(calculate_rsi)
    prices["macd"] = prices.groupby("ticker")["close"].transform(calculate_macd)

    if prices["ticker"].nunique() == 1:
        from ta.momentum import StochasticOscillator
        prices["stochastic"] = StochasticOscillator(
            high=prices["high"], low=prices["low"], close=prices["close"], window=14
        ).stoch()
    else:
        prices["stochastic"] = prices.groupby("ticker", group_keys=False).apply(calculate_stochastic)

    return prices


from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

sentiment_model = pipeline(
    "sentiment-analysis", model="ProsusAI/finbert", tokenizer="ProsusAI/finbert"
)


def get_sentiment_score(headline):
    try:
        result = sentiment_model(headline[:512])[0]  # FinBERT max 512 chars
        if result["label"] == "positive":
            return result["score"]
        elif result["label"] == "negative":
            return -result["score"]
        else:
            return 0.0
    except:
        return 0.0


def get_sentiment(news, prices):

    print("Scoring headlines... this may take a minute")
    news["sentiment"] = news["title"].apply(get_sentiment_score)

    news["date"] = news["published"].dt.date
    daily_sentiment = news.groupby(["ticker", "date"])["sentiment"].mean().reset_index()
    daily_sentiment.columns = ["ticker", "date", "sentiment_score"]

    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    features = prices.merge(daily_sentiment, on=["ticker", "date"], how="left")
    features["sentiment_score"] = features["sentiment_score"].fillna(0)

    return features


def create_target_and_split(features):
    features["target"] = (
        features.groupby("ticker")["close"].shift(-1) > features["close"]
    )
    features["target"] = features["target"].astype(int)

    ### How `shift(-1)` creates the target
    """
    | date     | close  | shift(-1) (tomorrow's close) | tomorrow > today? | target |
    |----------|--------|------------------------------|-------------------|--------|
    | May 27   | 440.36 | 442.10                       | 442.10 > 440.36 ✓ | 1 (up) |
    | May 28   | 442.10 | 438.36                       | 438.36 > 442.10 ✗ | 0 (down) |
    | May 29   | 438.36 | NaN                          | no tomorrow yet   | dropped |

    """

    feature_cols = [
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
    features_clean = features.dropna(subset=feature_cols + ["target"])

    data = features_clean.sort_values(by="date")

    dates = data["date"].unique()

    cutoff_idx = int(len(dates) * 0.8)

    cutoff_date = dates[cutoff_idx]

    train_df = data[data["date"] <= cutoff_date]
    test_df = data[data["date"] > cutoff_date]

    return train_df, test_df


def train_model(train_df, test_df):
    from xgboost import XGBClassifier

    feature_cols = [
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

    X_train = train_df[feature_cols]
    y_train = train_df["target"]

    X_test = test_df[feature_cols]
    y_test = test_df["target"]

    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    scale = neg / pos
    print(scale)

    model = XGBClassifier(
        n_estimators=300,  # 100 trees
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=scale,  #
        random_state=42,
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    import mlflow

    mlflow.set_tracking_uri("sqlite:///mlflow.db")

    mlflow.set_experiment("marketpulse_xgboost")

    with mlflow.start_run():
        mlflow.log_param("n_estimators", 300)
        mlflow.log_param("max_depth", 6)
        mlflow.log_param("learning_rate", 0.05)

        mlflow.log_metric("accuracy", accuracy_score(y_test, y_pred))
        mlflow.log_metric("precision", precision_score(y_test, y_pred))
        mlflow.log_metric("recall", recall_score(y_test, y_pred))
        mlflow.log_metric("f1", f1_score(y_test, y_pred))
        mlflow.xgboost.log_model(model, "model_1")

    print("Run logged successfully")

    import joblib

    joblib.dump(model, "models/model.pkl")


if __name__ == "__main__":
    prices, news = load_data()

    prices = build_features(prices)

    features = get_sentiment(news, prices)

    train_df, test_df = create_target_and_split(features)

    train_model(train_df, test_df)
