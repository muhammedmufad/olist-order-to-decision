"""Compare models and feature sets with time-based cross-validation."""
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from train_late_delivery import CATEGORICAL, NUMERIC, load_features

SELLER = ["seller_past_orders", "seller_past_late_rate"]
RECENT = ["recent_delivered_14d", "recent_late_rate_14d"]
BASE_NO_MONTH = [c for c in NUMERIC if c not in SELLER + RECENT + ["purchase_month"]]

FEATURE_SETS = {
    "base, no month": BASE_NO_MONTH,
    "+ seller, no month": BASE_NO_MONTH + SELLER,
    "+ seller + recent, no month": BASE_NO_MONTH + SELLER + RECENT,
}

MODELS = {
    "Logistic regression": lambda: LogisticRegression(max_iter=1000),
    "Gradient boosting": lambda: HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, random_state=42
    ),
}


def make_pipeline(model, numeric, categorical):
    prep = ColumnTransformer([
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), categorical),
    ])
    return Pipeline([("prep", prep), ("model", model)])


def main() -> None:
    df = load_features().sort_values("purchased_at").reset_index(drop=True)
    y = df["is_late"].astype(int).to_numpy()
    folds = list(TimeSeriesSplit(n_splits=3).split(df))

    for i, (train_idx, test_idx) in enumerate(folds, start=1):
        start = df.loc[test_idx[0], "purchased_at"]
        end = df.loc[test_idx[-1], "purchased_at"]
        print(f"Fold {i}: test {start:%Y-%m} to {end:%Y-%m}, "
              f"{len(test_idx):,} orders, {y[test_idx].mean():.1%} late")
    print()

    for model_name, make_model in MODELS.items():
        for set_name, numeric in FEATURE_SETS.items():
            X = df[numeric + CATEGORICAL]
            pr_aucs, lifts = [], []
            for train_idx, test_idx in folds:
                pipe = make_pipeline(make_model(), numeric, CATEGORICAL)
                pipe.fit(X.iloc[train_idx], y[train_idx])
                scores = pipe.predict_proba(X.iloc[test_idx])[:, 1]
                pr_auc = average_precision_score(y[test_idx], scores)
                pr_aucs.append(pr_auc)
                lifts.append(pr_auc / y[test_idx].mean())

            per_fold = ", ".join(f"{p:.3f}" for p in pr_aucs)
            print(f"{model_name:<20} {set_name:<28} "
                  f"PR-AUC per fold: {per_fold} | mean lift {np.mean(lifts):.2f}x")


if __name__ == "__main__":
    main()