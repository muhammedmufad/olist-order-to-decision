"""Export small result tables to reports/, so the dashboard runs without the warehouse."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from drift_check import CURRENT, MODEL_DIR, REFERENCE, psi_categorical, psi_numeric, status
from forecast_baselines import HORIZON, N_ORIGINS, load_demand
from forecast_intervals import HIGH_Q, LOW_Q, collect, forecast
from inventory_policy_table import SERVICE_LEVELS, smallest_target
from inventory_simulation import clustered_demand, error_series
from train_late_delivery import load_features

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def export_demand_and_forecast(wide) -> None:
    long = wide.reset_index().melt(id_vars="week_start", var_name="category", value_name="units")
    long.to_csv(REPORTS / "weekly_demand_top10.csv", index=False)

    # Same calibration as forecast_intervals.py
    n_weeks = len(wide)
    test_start = n_weeks - HORIZON - N_ORIGINS + 1
    calib = range(test_start - HORIZON - N_ORIGINS + 1, test_start - HORIZON + 1)
    ratios = np.array([actual / f for f, actual in collect(wide, calib) if f > 0])
    low, high = np.quantile(ratios, [LOW_Q, HIGH_Q])

    rows = []
    for category in wide.columns:
        f = forecast(wide[category].to_numpy(dtype=float))
        rows.append({"category": category, "forecast_per_week": round(f),
                     "low_80": round(f * low), "high_80": round(f * high)})
    (pd.DataFrame(rows).sort_values("forecast_per_week", ascending=False)
       .to_csv(REPORTS / "forecast_next_week.csv", index=False))


def export_stock_targets(wide) -> None:
    # Same order and seed as inventory_policy_table.py, so the numbers match the README.
    errors = dict(zip(wide.columns, error_series(wide)))
    rng = np.random.default_rng(42)
    rows = []
    for category in wide.sum().sort_values(ascending=False).index:
        mean_demand = forecast(wide[category].to_numpy(dtype=float))
        demand = clustered_demand([errors[category]], mean_demand, rng)
        row = {"category": category, "forecast_per_week": round(mean_demand)}
        for level in SERVICE_LEVELS:
            row[f"target_{round(level * 100)}"] = smallest_target(demand, mean_demand, level)[0]
        row["weeks_cover_95"] = round(row["target_95"] / mean_demand, 1)
        rows.append(row)
    pd.DataFrame(rows).to_csv(REPORTS / "stock_targets.csv", index=False)


def export_drift() -> None:
    meta = json.loads((MODEL_DIR / "late_delivery_model.json").read_text())
    model = joblib.load(MODEL_DIR / "late_delivery_model.joblib")
    numeric, categorical = meta["numeric_features"], meta["categorical_features"]

    df = load_features()
    ref = df[(df["purchased_at"] >= REFERENCE[0]) & (df["purchased_at"] < REFERENCE[1])]
    cur = df[(df["purchased_at"] >= CURRENT[0]) & (df["purchased_at"] < CURRENT[1])]

    rows = [{"feature": c, "psi": round(psi_numeric(ref[c], cur[c]), 3)} for c in numeric]
    rows += [{"feature": c, "psi": round(psi_categorical(ref[c], cur[c]), 3)} for c in categorical]
    psi = pd.DataFrame(rows).sort_values("psi", ascending=False)
    psi["status"] = psi["psi"].map(status)
    psi.to_csv(REPORTS / "drift_psi.csv", index=False)

    summary = [{
        "period": name,
        "orders": len(part),
        "avg_promised_days": round(part["promised_days"].mean(), 1),
        "mean_predicted_risk": round(float(model.predict_proba(part[numeric + categorical])[:, 1].mean()), 4),
        "actual_late_rate": round(float(part["is_late"].mean()), 4),
    } for name, part in [("reference", ref), ("current", cur)]]
    pd.DataFrame(summary).to_csv(REPORTS / "drift_summary.csv", index=False)


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    wide = load_demand()
    export_demand_and_forecast(wide)
    export_stock_targets(wide)
    export_drift()
    for path in sorted(REPORTS.glob("*.csv")):
        print(f"{path.name:<28} {len(pd.read_csv(path)):>5} rows")


if __name__ == "__main__":
    main()