"""Stock targets for the top 10 categories at three service levels.

Each category's demand is simulated from ITS OWN forecast-error history, drawn in
4-week blocks so that bad weeks cluster as in reality. Same assumptions as
inventory_simulation.py: hypothetical warehouse, weekly top-up, 2-week lead time.
"""
import numpy as np

from forecast_intervals import forecast
from inventory_simulation import (
    LEAD_TIME, RUNS, clustered_demand, error_series, load_demand, simulate,
)

SERVICE_LEVELS = [0.90, 0.95, 0.99]


def smallest_target(demand: np.ndarray, mean_demand: float, level: float):
    """Lowest stock target whose share of weeks without stockout reaches `level`."""
    for multiple in np.arange(1.5, 6.01, 0.05):
        target = round(mean_demand * multiple)
        result = simulate(target, demand)
        if result["service_level"] >= level:
            return target, result["avg_stock_left"]
    return None, None


def main() -> None:
    wide = load_demand()
    errors = dict(zip(wide.columns, error_series(wide)))   # each category's own errors
    rng = np.random.default_rng(42)

    print(f"Own-history clustered errors, lead time {LEAD_TIME} weeks, "
          f"{RUNS:,} simulated years per category\n")
    print(f"{'Category':<24}{'Forecast/wk':>12}{'90%':>7}{'95%':>7}{'99%':>7}"
          f"{'Cover @95%':>12}{'Left @95%':>11}")

    for category in wide.sum().sort_values(ascending=False).index:
        mean_demand = forecast(wide[category].to_numpy(dtype=float))
        demand = clustered_demand([errors[category]], mean_demand, rng)
        found = {level: smallest_target(demand, mean_demand, level) for level in SERVICE_LEVELS}
        t95, left95 = found[0.95]
        print(f"{category[:23]:<24}{mean_demand:>12.0f}"
              + "".join(f"{found[level][0]:>7}" for level in SERVICE_LEVELS)
              + f"{t95 / mean_demand:>11.1f}w{left95:>11.0f}")

    print("\n99% targets rest on about 38 weeks of history per category: treat them as rough.")


if __name__ == "__main__":
    main()