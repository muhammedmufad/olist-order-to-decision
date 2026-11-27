"""Train the final late-delivery model on all delivered orders and save it for the API."""
import json
from datetime import datetime
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression

from evaluate_cv import BASE_NO_MONTH, make_pipeline
from train_late_delivery import CATEGORICAL, load_features

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_FILE = MODEL_DIR / "late_delivery_model.joblib"
META_FILE = MODEL_DIR / "late_delivery_model.json"


def main() -> None:
    df = load_features()
    features = BASE_NO_MONTH + CATEGORICAL
    X, y = df[features], df["is_late"].astype(int)

    # The model chosen by cross-validation: logistic regression, base features, no month.
    pipe = make_pipeline(LogisticRegression(max_iter=1000), BASE_NO_MONTH, CATEGORICAL)
    pipe.fit(X, y)

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(pipe, MODEL_FILE)

    meta = {
        "model": "logistic regression",
        "chosen_by": "time-based cross-validation (mean lift 1.88x, see README)",
        "numeric_features": BASE_NO_MONTH,
        "categorical_features": CATEGORICAL,
        "trained_on_orders": len(df),
        "training_period": [str(df["purchased_at"].min().date()),
                            str(df["purchased_at"].max().date())],
        "training_late_rate": round(float(y.mean()), 4),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    META_FILE.write_text(json.dumps(meta, indent=2))

    print(f"Trained on {len(df):,} orders, late rate {y.mean():.1%}")
    print(f"Saved model: {MODEL_FILE} ({MODEL_FILE.stat().st_size / 1024:.0f} KB)")
    print(f"Saved metadata: {META_FILE}\n")

    # Sanity check: reload the saved file and score three real orders.
    reloaded = joblib.load(MODEL_FILE)
    sample = X.head(3)
    risks = reloaded.predict_proba(sample)[:, 1]
    for (_, row), risk in zip(sample.iterrows(), risks):
        print(f"  {row['customer_state']} <- {row['seller_state']}, "
              f"{row['distance_km']:.0f} km, promised {row['promised_days']} days: "
              f"late risk {risk:.1%}")


if __name__ == "__main__":
    main()