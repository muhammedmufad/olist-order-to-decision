"""Monte Carlo simulation of a weekly order-up-to inventory policy for one category.

ASSUMPTIONS (stated, not from the data):
- A hypothetical warehouse stocks the category (Olist sellers hold their own stock).
- Each week ends with an order that tops stock up to a target level.
- LEAD_TIME = 2: an order placed at the end of week w arrives at the start of week w+2.
- Demand that cannot be served is lost (the customer buys elsewhere).
- Demand = this week's forecast x a forecast error drawn from real past errors.

Two ways to draw the errors:
- independent: each week's error is drawn on its own, so bad weeks never cluster
- clustered: errors are drawn in blocks of 4 real consecutive weeks, so they cluster as in reality
"""
import numpy as np

from forecast_baselines import HORIZON, N_ORIGINS, load_demand
from forecast_intervals import forecast

CATEGORY = "bed_bath_table"
LEAD_TIME = 2
WEEKS = 60
WARMUP = 8
RUNS = 2000
TARGET_SERVICE = 0.95
BLOCK = 4            # consecutive real weeks per block in the clustered version


def error_series(wide) -> list:
    """Per category: actual / forecast for each week, in time order, from late Nov 2017."""
    n_weeks = len(wide)
    start = n_weeks - 2 * HORIZON - 2 * N_ORIGINS + 2      # same start as module 2's calibration
    series = []
    for category in wide.columns:
        s = wide[category].to_numpy(dtype=float)
        ratios = [s[t] / forecast(s[:t]) for t in range(start, n_weeks) if forecast(s[:t]) > 0]
        series.append(np.array(ratios))
    return series


def independent_demand(series, mean_demand, rng) -> np.ndarray:
    pool = np.concatenate(series)
    return mean_demand * rng.choice(pool, size=(RUNS, WEEKS))


def clustered_demand(series, mean_demand, rng) -> np.ndarray:
    demand = np.empty((RUNS, WEEKS))
    for run in range(RUNS):
        path = []
        while len(path) < WEEKS:
            s = series[rng.integers(len(series))]          # a random category's error history
            start = rng.integers(len(s) - BLOCK + 1)        # a random starting week in it
            path.extend(s[start:start + BLOCK])             # 4 real consecutive weeks
        demand[run] = mean_demand * np.array(path[:WEEKS])
    return demand


def simulate(order_up_to: float, demand: np.ndarray) -> dict:
    on_hand = np.full(RUNS, float(order_up_to))
    in_transit = [np.zeros(RUNS) for _ in range(LEAD_TIME)]
    served = wanted = stockout_weeks = stock_total = 0.0

    for week in range(WEEKS):
        on_hand += in_transit.pop(0)
        d = demand[:, week]
        sold = np.minimum(on_hand, d)
        if week >= WARMUP:
            served += sold.sum()
            wanted += d.sum()
            stockout_weeks += (d > on_hand).sum()
        on_hand -= sold
        if week >= WARMUP:
            stock_total += on_hand.sum()
        position = on_hand + sum(in_transit)
        in_transit.append(np.maximum(order_up_to - position, 0))

    counted = RUNS * (WEEKS - WARMUP)
    return {
        "service_level": 1 - stockout_weeks / counted,
        "fill_rate": served / wanted,
        "avg_stock_left": stock_total / counted,
    }


def main() -> None:
    wide = load_demand()
    series = error_series(wide)
    mean_demand = forecast(wide[CATEGORY].to_numpy(dtype=float))

    lag1 = np.mean([np.corrcoef(s[:-1], s[1:])[0, 1] for s in series])
    print(f"Lag-1 autocorrelation of weekly forecast errors (mean over categories): {lag1:.2f}")
    print("  0 = no clustering; positive = good and bad weeks come in runs\n")

    rng = np.random.default_rng(42)
    demands = {
        "independent": independent_demand(series, mean_demand, rng),
        "clustered": clustered_demand(series, mean_demand, rng),
    }

    print(f"Category: {CATEGORY}, forecast {mean_demand:.0f} units/week, "
          f"lead time {LEAD_TIME} weeks, {RUNS:,} simulated years\n")
    print(f"{'Target':>7} | {'Service: indep.':>15} {'clustered':>10} | "
          f"{'Stock left: indep.':>18} {'clustered':>10}")

    best = {}
    for multiple in np.arange(2.0, 5.01, 0.1):
        target = round(mean_demand * multiple)
        r = {mode: simulate(target, d) for mode, d in demands.items()}
        print(f"{target:>7} | {r['independent']['service_level']:>15.1%} "
              f"{r['clustered']['service_level']:>10.1%} | "
              f"{r['independent']['avg_stock_left']:>18.0f} "
              f"{r['clustered']['avg_stock_left']:>10.0f}")
        for mode in demands:
            if mode not in best and r[mode]["service_level"] >= TARGET_SERVICE:
                best[mode] = (target, r[mode]["avg_stock_left"])

    print()
    for mode, (target, stock) in best.items():
        print(f"{mode:>11}: {TARGET_SERVICE:.0%} weeks without stockout needs a target of "
              f"{target} units ({target / mean_demand:.1f} weeks), about {stock:.0f} left on the shelf")


if __name__ == "__main__":
    main()