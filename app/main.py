"""Late-delivery risk API: send an order's purchase-time details, get its risk back."""
import json
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
model = joblib.load(MODEL_DIR / "late_delivery_model.joblib")
meta = json.loads((MODEL_DIR / "late_delivery_model.json").read_text())

app = FastAPI(
    title="Olist late-delivery risk",
    description="Scores an order's risk of arriving late, using only information known at checkout.",
    version="1.0",
)


class Order(BaseModel):
    """Everything known about an order at the moment of purchase."""
    purchase_dow: int = Field(..., ge=0, le=6, description="Day of week, 0 = Sunday")
    purchase_hour: int = Field(..., ge=0, le=23)
    promised_days: int = Field(..., ge=0, description="Days until the promised delivery date")
    item_count: int = Field(..., ge=1)
    seller_count: int = Field(..., ge=1)
    items_value: float = Field(..., gt=0, description="Total item price in BRL")
    freight_value: float = Field(..., ge=0, description="Total shipping cost in BRL")
    main_item_weight_g: float | None = None
    distance_km: float | None = None
    main_category: str = "unknown"
    customer_state: str = Field(..., min_length=2, max_length=2)
    seller_state: str = Field(..., min_length=2, max_length=2)

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "purchase_dow": 1, "purchase_hour": 14, "promised_days": 20,
                "item_count": 1, "seller_count": 1,
                "items_value": 120.0, "freight_value": 45.0,
                "main_item_weight_g": 2000, "distance_km": 2700,
                "main_category": "bed_bath_table",
                "customer_state": "AM", "seller_state": "SP",
            }]
        }
    }


@app.get("/health")
def health() -> dict:
    """Is the service up, and which model is it using?"""
    return {"status": "ok", "model": meta["model"], "trained_at": meta["trained_at"]}


@app.post("/predict")
def predict(order: Order) -> dict:
    row = order.model_dump()
    # The same derived features the model was trained with.
    row["freight_ratio"] = row["freight_value"] / row["items_value"]
    row["same_state"] = str(row["customer_state"] == row["seller_state"])

    X = pd.DataFrame([row])[meta["numeric_features"] + meta["categorical_features"]]
    X[meta["numeric_features"]] = X[meta["numeric_features"]].astype(float)   # missing -> NaN

    risk = float(model.predict_proba(X)[0, 1])
    base = meta["training_late_rate"]
    return {
        "late_risk": round(risk, 4),
        "average_late_rate": base,
        "relative_to_average": round(risk / base, 2),
    }