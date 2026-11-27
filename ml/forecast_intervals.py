"""Build 80% prediction intervals for the 4-week-mean forecast, and check them on later weeks."""
import numpy as np

from forecast_baselines import HORIZON, N_ORIGINS, load_demand

COVERAGE = 0.80
LOW_Q, HIGH_Q = (1 - COVERAGE) / 2, 1 - (1 - COVERAGE) / 2   # 0.10 and 0.90


def forecast(history: np.ndarray) -> float:
    """The chosen baseline: the mean of the last 4 weeks."""
    return history[-4:].mean()


def collect(wide, origins):
    """For every category and origin: (forecast, actual) for each of the next weeks."""
    pairs = []
    for category in wide.columns:
        series = wide[category].to_numpy(dtype=float)
        for t in origins:
            f = forecast(series[:t])
            for step in range(HORIZON):
                pairs.append((f, series[t + step]))
    return pairs


def main() -> None:
    wide = load_demand()
    n_weeks = len(wide)

    # Test: the last 16 origins (same as the baseline comparison).
    test_start = n_weeks - HORIZON - N_ORIGINS + 1
    test_origins = range(test_start, n_weeks - HORIZON + 1)
    # Calibration: 16 earlier origins whose answers were all known before the test begins.
    calib_origins = range(test_start - HORIZON - N_ORIGINS + 1, test_start - HORIZON + 1)

    # 1. Learn how wrong the forecast usually is, on the calibration period only.
    calib = collect(wide, calib_origins)
    ratios = np.array([actual / f for f, actual in calib if f > 0])
    low, high = np.quantile(ratios, [LOW_Q, HIGH_Q])
    print(f"Calibration: {len(ratios)} forecasts, origins from "
          f"{wide.index[calib_origins[0]]:%Y-%m-%d}")
    print(f"Actual / forecast: 10th percentile {low:.2f}, 90th percentile {high:.2f}")
    print(f"80% interval = forecast x {low:.2f} to forecast x {high:.2f}\n")

    # 2. Check the interval on the later test period.
    test = collect(wide, test_origins)
    inside = [f * low <= actual <= f * high for f, actual in test]
    width = [f * (high - low) for f, actual in test]
    print(f"Test: {len(test)} forecasts, origins from {wide.index[test_origins[0]]:%Y-%m-%d}")
    print(f"Actual inside the interval: {np.mean(inside):.1%} (target {COVERAGE:.0%})")
    print(f"Average interval width: {np.mean(width):.0f} units\n")

    # 3. One concrete forecast from the end of the data, for the biggest category.
    biggest = wide.sum().idxmax()
    f = forecast(wide[biggest].to_numpy(dtype=float))
    print(f"Next weeks for {biggest}: about {f:.0f} units per week, "
          f"80% interval {f * low:.0f} to {f * high:.0f}")


if __name__ == "__main__":
    main()