"""Olist order-to-decision: interactive dashboard over the project's saved model and results."""
import json
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
MODELS, REPORTS = ROOT / "models", ROOT / "reports"
REPO_URL = "https://github.com/muhammedmufad/olist-order-to-decision"

STATES = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
          "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

st.set_page_config(page_title="Olist order-to-decision", layout="wide")


@st.cache_resource
def load_model():
    model = joblib.load(MODELS / "late_delivery_model.joblib")
    meta = json.loads((MODELS / "late_delivery_model.json").read_text())
    return model, meta


@st.cache_data
def load_report(name: str) -> pd.DataFrame:
    return pd.read_csv(REPORTS / name)


model, meta = load_model()
demand = load_report("weekly_demand_top10.csv")
forecast_df = load_report("forecast_next_week.csv")
stock = load_report("stock_targets.csv")
psi = load_report("drift_psi.csv")
drift = load_report("drift_summary.csv")
ref, cur = drift.iloc[0], drift.iloc[1]

st.title("Olist order-to-decision")
st.write("From 99,441 real e-commerce orders to decisions: late-delivery risk, demand forecasts, "
         f"stock targets and model monitoring. Method, code and limitations: [GitHub repository]({REPO_URL}).")

tab_risk, tab_stock, tab_drift, tab_ab = st.tabs(
    ["Late-delivery risk", "Demand and stock", "Drift monitor", "A/B test"])

# ---------- Tab 1: score one order ----------
with tab_risk:
    st.subheader("How likely is this order to arrive late?")
    st.caption("Single-item order, scored with only information known at checkout. "
               "Logistic regression chosen by time-based cross-validation.")
    c1, c2, c3 = st.columns(3)
    with c1:
        customer_state = st.selectbox("Customer state", STATES, index=STATES.index("AM"))
        seller_state = st.selectbox("Seller state", STATES, index=STATES.index("SP"))
        distance_km = st.number_input("Distance seller to customer (km)", 0, 5000, 2700)
    with c2:
        promised_days = st.number_input("Promised delivery (days)", 1, 120, 20)
        items_value = st.number_input("Item value (BRL)", 1.0, 10000.0, 120.0)
        freight_value = st.number_input("Freight (BRL)", 0.0, 1000.0, 45.0)
    with c3:
        category = st.selectbox("Main category", list(stock["category"]) + ["unknown"])
        weight = st.number_input("Item weight (g)", 0, 50000, 2000)
        weekday = st.selectbox("Purchase day", WEEKDAYS, index=1)
        purchase_hour = st.slider("Purchase hour", 0, 23, 14)

    row = {
        "purchase_dow": WEEKDAYS.index(weekday), "purchase_hour": purchase_hour,
        "promised_days": promised_days, "item_count": 1, "seller_count": 1,
        "items_value": items_value, "freight_value": freight_value,
        "freight_ratio": freight_value / items_value,
        "main_item_weight_g": weight, "distance_km": distance_km,
        "main_category": category, "customer_state": customer_state,
        "seller_state": seller_state, "same_state": str(customer_state == seller_state),
    }
    X = pd.DataFrame([row])[meta["numeric_features"] + meta["categorical_features"]]
    X[meta["numeric_features"]] = X[meta["numeric_features"]].astype(float)
    risk = float(model.predict_proba(X)[0, 1])
    base = meta["training_late_rate"]

    m1, m2 = st.columns(2)
    m1.metric("Late-delivery risk", f"{risk:.1%}")
    m2.metric("Compared with the average order", f"{risk / base:.1f}×",
              help=f"Average late rate in training data: {base:.1%}")
    st.warning(f"Drift check: from May 2018 the model overestimated risk (predicted "
               f"{cur.mean_predicted_risk:.1%} vs actual {cur.actual_late_rate:.1%}). "
               "Read the result as a ranking, riskier or safer than average, not as an exact probability.")

# ---------- Tab 2: demand and stock ----------
with tab_stock:
    st.subheader("Weekly demand and recommended stock")
    chosen = st.selectbox("Category", list(stock["category"]), key="stock_category")
    history = demand[demand["category"] == chosen].set_index("week_start")["units"]
    st.line_chart(history)

    f = forecast_df.set_index("category").loc[chosen]
    s = stock.set_index("category").loc[chosen]
    a, b, c = st.columns(3)
    a.metric("Forecast, next week", f"{f.forecast_per_week:.0f} units")
    b.metric("80% range", f"{f.low_80:.0f} to {f.high_80:.0f}")
    c.metric("Stock target for 95% service", f"{s.target_95:.0f} units",
             help=f"{s.weeks_cover_95} weeks of forecast demand")
    st.caption("Forecast: mean of the last 4 weeks (WAPE 27.6% in rolling evaluation). Stock targets: Monte Carlo "
               "simulation of 2,000 years, weekly reordering, 2-week lead time, hypothetical warehouse.")
    st.dataframe(stock, hide_index=True)

# ---------- Tab 3: drift monitor ----------
with tab_drift:
    st.subheader("Do recent orders still look like the training data?")
    st.caption("Reference: Jan 2017 to Apr 2018. Current: May to Aug 2018. "
               "PSI below 0.10 stable, 0.10 to 0.25 watch, above 0.25 drift.")
    st.dataframe(psi, hide_index=True)
    a, b, c = st.columns(3)
    a.metric("Promised delivery (current)", f"{cur.avg_promised_days:.1f} days",
             f"{cur.avg_promised_days - ref.avg_promised_days:+.1f} days", delta_color="off")
    b.metric("Model's average predicted risk", f"{cur.mean_predicted_risk:.1%}",
             f"{(cur.mean_predicted_risk - ref.mean_predicted_risk) * 100:+.1f} points", delta_color="off")
    c.metric("Actual late rate", f"{cur.actual_late_rate:.1%}",
             f"{(cur.actual_late_rate - ref.actual_late_rate) * 100:+.1f} points", delta_color="off")
    st.info("From May 2018 Olist promised deliveries about 3 days sooner and still delivered on time more often. "
            "The model, trained mostly on the older pattern, raised its risk estimates just as real lateness "
            "fell: a case for recalibrating or retraining on recent data.")

# ---------- Tab 4: A/B test ----------
with tab_ab:
    st.subheader("Cookie Cats: does moving the first gate from level 30 to level 40 change retention?")
    ab = pd.DataFrame({
        "Metric": ["1-day retention", "7-day retention"],
        "gate_30": ["44.82%", "19.02%"],
        "gate_40": ["44.23%", "18.20%"],
        "Difference": ["-0.59 points", "-0.82 points"],
        "p-value": ["0.074", "0.0016"],
        "95% interval": ["-1.24 to +0.06", "-1.33 to -0.31"],
    })
    st.dataframe(ab, hide_index=True)
    st.success("Decision: keep the gate at level 30. 7-day retention fell significantly with the later gate; "
               "the 1-day result is inconclusive.")
    st.warning("Caveat: the groups are unevenly sized (49.56% vs 50.44%, p = 0.0086), a sample ratio mismatch "
               "that could not be investigated without assignment logs.")
    st.caption("Results from ml/ab_cookie_cats.py (z-test and bootstrap agree).")