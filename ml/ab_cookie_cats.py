"""Cookie Cats A/B test. Step 2: was the split fair, and was the test big enough?"""
from pathlib import Path

import duckdb
import numpy as np
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "warehouse" / "olist.duckdb"

ALPHA = 0.05      # significance level: 5% risk of a false alarm
POWER = 0.80      # chance of detecting a true effect of the MDE size


def load():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("select * from main.stg_cookie_cats").df()
    con.close()
    return df


def sample_ratio_check(df) -> None:
    counts = df["variant"].value_counts().sort_index()
    expected = [len(df) / 2] * 2                       # what a perfect 50/50 split would give
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
    """Smallest true difference in a rate that the test detects with the chosen power."""
    z_alpha = stats.norm.ppf(1 - ALPHA / 2)
    z_power = stats.norm.ppf(POWER)
    return (z_alpha + z_power) * np.sqrt(2 * p_base * (1 - p_base) / n_per_group)


def main() -> None:
    df = load()
    sample_ratio_check(df)

    control = df[df["variant"] == "gate_30"]
    treatment = df[df["variant"] == "gate_40"]
    n = min(len(control), len(treatment))

    print(f"2. Power: smallest detectable difference (alpha {ALPHA}, power {POWER:.0%})")
    for column, label in [("retained_day1", "Day-1 retention"), ("retained_day7", "Day-7 retention")]:
        p0, p1 = control[column].mean(), treatment[column].mean()
        mde = minimum_detectable_effect(p0, n)
        verdict = "larger" if abs(p1 - p0) >= mde else "SMALLER"
        print(f"   {label}: observed {(p1 - p0) * 100:+.2f} points, "
              f"detectable {mde * 100:.2f} points -> observed is {verdict} than detectable")

    print("\n3. Game rounds in the first 14 days")
    summary = df.groupby("variant")["game_rounds_14d"].describe(percentiles=[0.5, 0.9, 0.99])
    print(summary[["count", "mean", "50%", "90%", "99%", "max"]].round(1).to_string())


if __name__ == "__main__":
    main()