"""Automated tests for the late-delivery risk API."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)   # calls the API directly, no server or browser needed

BASE_ORDER = {
    "purchase_dow": 1, "purchase_hour": 14, "promised_days": 20,
    "item_count": 1, "seller_count": 1,
    "items_value": 120.0, "freight_value": 45.0,
    "main_item_weight_g": 2000, "distance_km": 2700,
    "main_category": "bed_bath_table",
    "customer_state": "AM", "seller_state": "SP",
}


def order(**changes) -> dict:
    """A copy of the base order with some fields changed."""
    return {**BASE_ORDER, **changes}


def risk(payload: dict) -> float:
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    return response.json()["late_risk"]


def test_health_reports_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_returns_a_probability():
    assert 0.0 <= risk(order()) <= 1.0


def test_distant_order_is_riskier_than_local_order():
    far = risk(order())
    local = risk(order(customer_state="SP", distance_km=20))
    assert far > local


def test_rejects_impossible_hour():
    response = client.post("/predict", json=order(purchase_hour=25))
    assert response.status_code == 422


def test_missing_distance_is_allowed():
    payload = order()
    del payload["distance_km"]            # optional: the model fills in the median
    assert 0.0 <= risk(payload) <= 1.0


def test_unknown_category_is_allowed():
    assert 0.0 <= risk(order(main_category="category_never_seen")) <= 1.0