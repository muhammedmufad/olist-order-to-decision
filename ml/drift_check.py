"""Drift check: do recent orders look like the data the model learned from?"""
import json
from pathlib import Path

import joblib
import numpy as np

from train_late_delivery import load_features

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
REFERENCE = ("2017-01-01", "2018-05-01")   # what "normal" looked like
CURRENT = ("2018-05-01", "2018-09-01")     # the period being checked
EPS = 1e-4                                 # avoids dividing by zero for empty ranges


def psi_numeric(ref, cur, bins: int = 10) -> float:
    ref, cur = ref.dropna(), cur.dropna()
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.clip(np.histogram(ref, edges)[0] / len(ref), EPS, None)
    c = np.clip(np.histogram(cur, edges)[0] / len(cur), EPS, None)
    return float(np.sum((c - r) * np.log(c / r)))


def psi_categorical(ref, cur) -> float:
    r = ref.fillna("missing").value_counts(normalize=True)
    c = cur.fillna("missing").value_counts(normalize=True)
    categories = r.index.union(c.index)
    r = r.reindex(categories, fill_value=0).clip(lower=EPS)
    c = c.reindex(categories, fill_value=0).clip(lower=EPS)
    return float(np.sum((c - r) * np.log(c / r)))


def status(psi: float) -> str:
    return "stable" if psi < 0.10 else "watch" if psi < 0.25 else "DRIFT"


def main() -> None:
    meta = json.loads((MODEL_DIR / "late_delivery_model.json").read_text())
    model = joblib.load(MODEL_DIR / "late_delivery_model.joblib")
    numeric, categorical = meta["numeric_features"], meta["categorical_features"]

    df = load_features()
    ref = df[(df["purchased_at"] >= REFERENCE[0]) & (df["purchased_at"] < REFERENCE[1])]
    cur = df[(df["purchased_at"] >= CURRENT[0]) & (df["purchased_at"] < CURRENT[1])]
    print(f"Reference: {len(ref):,} orders ({REFERENCE[0]} to {REFERENCE[1]})")
    print(f"Current:   {len(cur):,} orders ({CURRENT[0]} to {CURRENT[1]})\n")

    print("1. Input drift  (PSI: below 0.10 stable, 0.10-0.25 watch, above 0.25 drift)")
    results = [(col, psi_numeric(ref[col], cur[col])) for col in numeric]
    results += [(col, psi_categorical(ref[col], cur[col])) for col in categorical]
    for col, psi in sorted(results, key=lambda item: -item[1]):
        print(f"   {col:<22} PSI {psi:6.3f}  {status(psi)}")

    print("\n2. Prediction and outcome drift")
    for name, part in [("reference", ref), ("current", cur)]:
        predicted = model.predict_proba(part[numeric + categorical])[:, 1].mean()
        print(f"   {name:<10} mean predicted risk {predicted:.1%}, "
              f"actual late rate {part['is_late'].mean():.1%}")

    print("\n3. Does the alarm work?  SIMULATED test, not real data:")
    shifted = cur["distance_km"] * 1.5
    psi = psi_numeric(ref["distance_km"], shifted)
    print(f"   distance_km made 50% longer: PSI {psi:.3f}  {status(psi)}")


if __name__ == "__main__":
    main()