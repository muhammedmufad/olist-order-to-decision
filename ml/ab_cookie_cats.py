"""Cookie Cats A/B test.
Step 2: was the split fair, and was the test big enough?
Step 3: is the difference in retention real?
"""
from pathlib import Path

import duckdb
import numpy as np
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "warehouse" / "olist.duckdb"

ALPHA = 0.05        # significance level: 5% risk of a false alarm
POWER = 0.80        # chance of detecting a true effect of the MDE size
BOOTSTRAPS = 10_000


def load():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("select * from main.stg_cookie_cats").df()
    con.close()
    return df


def sample_ratio_check(df) -> None:
    counts = df["variant"].value_counts().sort_index()
    expected = [len(df) / 2] * 2
    chi2, p = stats.chisquare(counts.to_numpy(), f_exp=expected)
    print("1. Sample ratio check (expected 50/50)")
    for variant, n in counts.items():
        print(f"   {variant}: {n:,} players ({n / len(df):.2%})")
    print(f"   chi-square = {chi2:.2f}, p = {p:.4f}")
    if p < 0.01:
        print("   WARNING: the split is unlikely to be 50/50 by chance (possible sample ratio mismatch)\n")
    else:
        print("   OK: the split is consistent with 50/50\n")


def minimum_detectable_effect(p_base: float, n_per_group: int) -> float:
    z_alpha = stats.norm.ppf(1 - ALPHA / 2)
    z_power = stats.norm.ppf(POWER)
    return (z_alpha + z_power) * np.sqrt(2 * p_base * (1 - p_base) / n_per_group)


def z_test(x0: int, n0: int, x1: int, n1: int):
    """Two-proportion z-test. Returns (difference, p-value, 95% CI low, CI high)."""
    p0, p1 = x0 / n0, x1 / n1
    diff = p1 - p0
    pooled = (x0 + x1) / (n0 + n1)                                  # assumes no true difference
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n0 + 1 / n1))
    p_value = 2 * stats.norm.sf(abs(diff / se_pooled))
    se = np.sqrt(p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1)          # for the interval
    z = stats.norm.ppf(1 - ALPHA / 2)
    return diff, p_value, diff - z * se, diff + z * se


def bootstrap_ci(x0: int, n0: int, x1: int, n1: int, seed: int = 42):
    """Bootstrap 95% CI of the difference. Re-sampling yes/no answers = binomial draws."""
    rng = np.random.default_rng(seed)
    p0_sim = rng.binomial(n0, x0 / n0, BOOTSTRAPS) / n0
    p1_sim = rng.binomial(n1, x1 / n1, BOOTSTRAPS) / n1
    diffs = p1_sim - p0_sim
    return np.quantile(diffs, [ALPHA / 2, 1 - ALPHA / 2]), (diffs < 0).mean()


def main() -> None:
    df = load()
    sample_ratio_check(df)

    control = df[df["variant"] == "gate_30"]
    treatment = df[df["variant"] == "gate_40"]
    n0, n1 = len(control), len(treatment)
    metrics = [("retained_day1", "Day-1 retention"), ("retained_day7", "Day-7 retention")]

    print(f"2. Power: smallest detectable difference (alpha {ALPHA}, power {POWER:.0%})")
    for column, label in metrics:
        p0, p1 = control[column].mean(), treatment[column].mean()
        mde = minimum_detectable_effect(p0, min(n0, n1))
        verdict = "larger" if abs(p1 - p0) >= mde else "SMALLER"
        print(f"   {label}: observed {(p1 - p0) * 100:+.2f} points, "
              f"detectable {mde * 100:.2f} points -> observed is {verdict} than detectable")

    print("\n3. Is the difference real? (gate_40 minus gate_30)")
    for column, label in metrics:
        x0, x1 = int(control[column].sum()), int(treatment[column].sum())
        diff, p_value, low, high = z_test(x0, n0, x1, n1)
        (b_low, b_high), share_negative = bootstrap_ci(x0, n0, x1, n1)
        relative = diff / (x0 / n0)
        print(f"   {label}: {diff * 100:+.2f} points ({relative:+.1%} relative)")
        print(f"      z-test:    p = {p_value:.4f}, 95% CI {low * 100:+.2f} to {high * 100:+.2f} points")
        print(f"      bootstrap: 95% CI {b_low * 100:+.2f} to {b_high * 100:+.2f} points, "
              f"gate_40 worse in {share_negative:.1%} of simulations")

    print("\n4. Game rounds in the first 14 days")
    summary = df.groupby("variant")["game_rounds_14d"].describe(percentiles=[0.5, 0.9, 0.99])
    print(summary[["count", "mean", "50%", "90%", "99%", "max"]].round(1).to_string())


if __name__ == "__main__":
    main()