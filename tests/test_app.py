"""
tests/test_app.py
Unit tests for Scholarship Predictor
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c


# --- Route tests ---

def test_welcome_page(client):
    r = client.get("/")
    assert r.status_code == 200

def test_academic_page_get(client):
    r = client.get("/academic")
    assert r.status_code == 200

def test_academic_invalid_zscore(client):
    r = client.post("/academic", data={"z_score": "9.9", "stream": "Arts"})
    assert b"Z-score" in r.data or r.status_code == 200

def test_academic_valid_zscore(client):
    r = client.post("/academic", data={
        "z_score": "1.5", "stream": "Science",
        "grade1": "A", "grade2": "B", "grade3": "C"
    }, follow_redirects=False)
    assert r.status_code == 302

def test_family_page_get(client):
    r = client.get("/family")
    assert r.status_code == 200

def test_family_invalid_income(client):
    r = client.post("/family", data={
        "annual_income": "9999999", "district": "Colombo"
    })
    assert r.status_code == 200

def test_family_valid_income(client):
    r = client.post("/family", data={
        "annual_income": "300000", "district": "Colombo"
    }, follow_redirects=False)
    assert r.status_code == 302

def test_predict_requires_login(client):
    r = client.post("/predict")
    assert r.status_code in (302, 401, 403)

def test_results_page(client):
    r = client.get("/results")
    assert r.status_code == 200

def test_reset_redirects(client):
    r = client.get("/reset")
    assert r.status_code == 302

def test_api_districts(client):
    r = client.get("/api/districts")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert "Colombo" in data

def test_api_schemes(client):
    r = client.get("/api/schemes")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) >= 6

def test_404_page(client):
    r = client.get("/nonexistent-page")
    assert r.status_code == 404


# --- Prediction logic tests ---

from scholarship_predictor import predict_for_student, DISTRICT_FACTORS, STREAM_CODES

def test_predict_returns_list():
    profile = {
        "z_score": 1.8, "stream": "Science",
        "grade_a_count": 2, "annual_income_lkr": 300000,
        "district": "Colombo"
    }
    results = predict_for_student(profile)
    assert isinstance(results, list)
    assert len(results) == 6

def test_predict_has_required_keys():
    profile = {
        "z_score": 1.5, "stream": "Arts",
        "grade_a_count": 1, "annual_income_lkr": 200000,
        "district": "Kandy"
    }
    results = predict_for_student(profile)
    for r in results:
        assert "scheme_id" in r
        assert "eligible" in r
        assert "probability_pct" in r

def test_high_zscore_more_eligible():
    high = predict_for_student({
        "z_score": 2.5, "stream": "Science",
        "grade_a_count": 3, "annual_income_lkr": 100000,
        "district": "Colombo"
    })
    low = predict_for_student({
        "z_score": 0.6, "stream": "Arts",
        "grade_a_count": 0, "annual_income_lkr": 4000000,
        "district": "Colombo"
    })
    high_count = sum(1 for r in high if r["eligible"])
    low_count  = sum(1 for r in low  if r["eligible"])
    assert high_count >= low_count

def test_district_factors_loaded():
    assert len(DISTRICT_FACTORS) >= 25

def test_stream_codes_loaded():
    assert "Biological Science" in STREAM_CODES
    assert "Arts" in STREAM_CODES
