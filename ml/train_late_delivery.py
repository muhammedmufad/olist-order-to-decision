"""Train and evaluate baseline models for late-delivery risk on a time-based split."""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "warehouse" / "olist.duckdb"
SPLIT_DATE = "2018-04-01"

NUMERIC = [
    "purchase_month", "purchase_dow", "purchase_hour", "promised_days",
    "item_count", "seller_count", "items_value", "freight_value",
    "freight_ratio", "main_item_weight_g",
]
CATEGORICAL = ["main_category", "customer_state", "seller_state", "same_state"]


def load_features() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("select * from main.ml_late_delivery_features").df()
    con.close()
    df["same_state"] = df["same_state"].astype(str)
    return df


def build_preprocessor() -> ColumnTransformer:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric, NUMERIC),
        ("cat", categorical, CATEGORICAL),
    ])


def top_share_metrics(y_true: np.ndarray, scores: np.ndarray, share: float = 0.10):
    """Flag the riskiest `share` of orders. Return (precision, recall) of that flag."""
    n_flagged = int(len(scores) * share)
    flagged = np.argsort(scores)[::-1][:n_flagged]
    caught = y_true[flagged].sum()
    return caught / n_flagged, caught / y_true.sum()


def main() -> None:
    df = load_features()
    train = df[df["purchased_at"] < SPLIT_DATE]
    test = df[df["purchased_at"] >= SPLIT_DATE]

    X_train, y_train = train[NUMERIC + CATEGORICAL], train["is_late"].astype(int)
    X_test, y_test = test[NUMERIC + CATEGORICAL], test["is_late"].astype(int).to_numpy()

    print(f"Train: {len(train):,} orders, {y_train.mean():.1%} late")
    print(f"Test:  {len(test):,} orders, {y_test.mean():.1%} late")
    print(f"PR-AUC of random guessing = test late rate = {y_test.mean():.3f}\n")

    models = {
        "Logistic regression": LogisticRegression(max_iter=1000),
        "Gradient boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, random_state=42
        ),
    }

    for name, model in models.items():
        pipe = Pipeline([("prep", build_preprocessor()), ("model", model)])
        pipe.fit(X_train, y_train)
        scores = pipe.predict_proba(X_test)[:, 1]

        precision, recall = top_share_metrics(y_test, scores)
        print(f"{name}")
        print(f"  PR-AUC:  {average_precision_score(y_test, scores):.3f}")
        print(f"  ROC-AUC: {roc_auc_score(y_test, scores):.3f}")
        print(f"  Flag riskiest 10%: precision {precision:.1%}, recall {recall:.1%}\n")


if __name__ == "__main__":
    main()