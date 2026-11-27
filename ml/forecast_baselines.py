"""Compare simple weekly demand forecasts for the top categories with a rolling evaluation."""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "warehouse" / "olist.duckdb"

TOP_N = 10        # forecast the 10 biggest categories
HORIZON = 4       # forecast 4 weeks ahead
N_ORIGINS = 16    # how many times we stand at a week and forecast ahead


def load_demand() -> pd.DataFrame:
    """One column per top category, one row per week."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(
        "select week_start, category, units from main.mart_weekly_category_demand"
    ).df()
    con.close()
    top = df.groupby("category")["units"].sum().nlargest(TOP_N).index
    return (
        df[df["category"].isin(top)]
        .pivot(index="week_start", columns="category", values="units")
        .sort_index()
    )


METHODS = {
    "Naive (last week)":     lambda history: np.repeat(history[-1], HORIZON),
    "Mean of last 4 weeks":  lambda history: np.repeat(history[-4:].mean(), HORIZON),
    "Mean of last 8 weeks":  lambda history: np.repeat(history[-8:].mean(), HORIZON),
    "Mean of last 12 weeks": lambda history: np.repeat(history[-12:].mean(), HORIZON),
}


def main() -> None:
    wide = load_demand()
    n_weeks = len(wide)
    origins = range(n_weeks - HORIZON - N_ORIGINS + 1, n_weeks - HORIZON + 1)

    first_origin = wide.index[origins[0]]
    print(f"{len(wide.columns)} categories, {n_weeks} weeks")
    print(f"Forecasting {HORIZON} weeks ahead from {N_ORIGINS} points, "
          f"starting {first_origin:%Y-%m-%d}\n")

    for name, method in METHODS.items():
        total_abs_error, total_actual = 0.0, 0.0
        for category in wide.columns:
            series = wide[category].to_numpy(dtype=float)
            for t in origins:
                history = series[:t]              # everything before week t: allowed
                actual = series[t:t + HORIZON]    # the next 4 weeks: the answer
                forecast = method(history)
                total_abs_error += np.abs(forecast - actual).sum()
                total_actual += actual.sum()
        print(f"{name:<24} WAPE {total_abs_error / total_actual:.1%}")


if __name__ == "__main__":
    main()