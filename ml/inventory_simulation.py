"""Monte Carlo simulation of a weekly order-up-to inventory policy for one category.

ASSUMPTIONS (stated, not from the data):
- A hypothetical warehouse stocks the category (Olist sellers hold their own stock).
- Each week ends with an order that tops stock up to a target level.
- LEAD_TIME = 2: an order placed at the end of week w arrives at the start of week w+2.
- Demand that cannot be served is lost (the customer buys elsewhere).
"""
import numpy as np

from forecast_baselines import HORIZON, N_ORIGINS, load_demand
from forecast_intervals import collect, forecast

CATEGORY = "bed_bath_table"
LEAD_TIME = 2        # weeks from placing an order to receiving it (assumption)
WEEKS = 60           # weeks simulated per run
WARMUP = 8           # first weeks ignored, while the simulation settles
RUNS = 2000          # number of simulated years
TARGET_SERVICE = 0.95


def error_ratios(wide) -> np.ndarray:
    """Every actual/forecast ratio from all past rolling forecasts (module 2's error pattern)."""
    n_weeks = len(wide)
    test_start = n_weeks - HORIZON - N_ORIGINS + 1
    origins = range(test_start - HORIZON - N_ORIGINS + 1, n_weeks - HORIZON + 1)
    return np.array([actual / f for f, actual in collect(wide, origins) if f > 0])


def simulate(order_up_to: float, mean_demand: float, ratios: np.ndarray, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    demand = mean_demand * rng.choice(ratios, size=(RUNS, WEEKS))   # 2,000 invented years

    on_hand = np.full(RUNS, float(order_up_to))
    in_transit = [np.zeros(RUNS) for _ in range(LEAD_TIME)]          # orders on their way
    served = wanted = stockout_weeks = stock_total = 0.0

    for week in range(WEEKS):
        on_hand += in_transit.pop(0)                  # the oldest order arrives
        d = demand[:, week]
        sold = np.minimum(on_hand, d)                 # can't sell more than we have
        if week >= WARMUP:
            served += sold.sum()
            wanted += d.sum()
            stockout_weeks += (d > on_hand).sum()
        on_hand -= sold
        if week >= WARMUP:
            stock_total += on_hand.sum()
        position = on_hand + sum(in_transit)          # what we have plus what's coming
        in_transit.append(np.maximum(order_up_to - position, 0))   # top up to the target

    counted = RUNS * (WEEKS - WARMUP)
    return {
        "service_level": 1 - stockout_weeks / counted,
        "fill_rate": served / wanted,
        "avg_stock_left": stock_total / counted,
    }


def main() -> None:
    wide = load_demand()
    ratios = error_ratios(wide)
    mean_demand = forecast(wide[CATEGORY].to_numpy(dtype=float))

    print(f"Category: {CATEGORY}, forecast {mean_demand:.0f} units/week, "
          f"lead time {LEAD_TIME} weeks, {RUNS:,} simulated years\n")
    print(f"{'Target stock':>12} {'Weeks w/o stockout':>19} {'Fill rate':>10} {'Avg stock left':>15}")

    best = None
    for multiple in np.arange(1.5, 4.01, 0.1):
        target = round(mean_demand * multiple)
        r = simulate(target, mean_demand, ratios)
        print(f"{target:>12} {r['service_level']:>19.1%} {r['fill_rate']:>10.1%} "
              f"{r['avg_stock_left']:>15.0f}")
        if best is None and r["service_level"] >= TARGET_SERVICE:
            best = (target, r)

    if best:
        target, r = best
        print(f"\nSmallest target reaching {TARGET_SERVICE:.0%} weeks without stockout: "
              f"{target} units ({target / mean_demand:.1f} weeks of forecast demand), "
              f"leaving about {r['avg_stock_left']:.0f} units on the shelf on average.")


if __name__ == "__main__":
    main()