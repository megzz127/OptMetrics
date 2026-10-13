"""
Automated integration tests for OptMetrics REST API endpoints.
Tests Profile, Custom Fields, Form Analysis, Review, Exporters,
History, Analytics, and Settings.
"""

import os
import tempfile
import pytest
from app import create_app


@pytest.fixture
def client():
    # Create a temporary file to use as the test database
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["OPTMETRICS_DB_PATH"] = db_path

    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"


def test_seed_and_get_profile(client):
    # Seed sample profile
    seed_res = client.post("/api/profile/seed-sample")
    assert seed_res.status_code == 200

    # Retrieve profile
    get_res = client.get("/api/profile")
    assert get_res.status_code == 200
    profile = get_res.get_json()["profile"]
    assert profile["full_name"] == "Alex J. Morgan"
    assert profile["email"] == "alex.morgan.tech@example.com"
    assert "Python" in profile["skills"]
    assert len(profile["custom_fields"]) > 0


def test_update_profile_and_custom_field(client):
    # Update profile
    update_res = client.put("/api/profile", json={
        "full_name": "Taylor Swift",
        "email": "taylor@example.org",
        "phone": "+1-555-999-8888",
        "college": "Global University",
        "degree": "B.S. Data Science",
        "branch": "Data Science",
        "graduation_year": "2024",
        "skills": ["Python", "SQL"]
    })
    assert update_res.status_code == 200

    # Add custom field
    cf_res = client.post("/api/profile/custom-field", json={
        "field_label": "Portfolio Website",
        "field_value": "https://taylorswift.dev",
        "field_type": "url"
    })
    assert cf_res.status_code == 201
    cf_data = cf_res.get_json()["custom_field"]
    assert cf_data["field_key"] == "portfolio_website"

    # Delete custom field
    del_res = client.delete(f"/api/profile/custom-field/{cf_data['id']}")
    assert del_res.status_code == 200


def test_analyze_form_and_export(client):
    # Seed profile first
    client.post("/api/profile/seed-sample")

    # Analyze pasted form questions
    raw_input = """
    1. Applicant Name
    2. Email Address
    3. University / College
    4. Current Degree
    5. Expected Graduation Year
    6. Technical Skills
    """
    analyze_res = client.post("/api/forms/analyze", json={
        "form_name": "Internship 2025 Test Form",
        "source": "pasted",
        "raw_input": raw_input
    })
    assert analyze_res.status_code == 201
    data = analyze_res.get_json()
    assert data["total_fields"] == 6
    assert data["matched_fields"] >= 5
    session_id = data["session_id"]
    suggestions = data["suggestions"]
    assert len(suggestions) == 6

    # Test approve-all
    approve_res = client.post(f"/api/forms/sessions/{session_id}/approve-all")
    assert approve_res.status_code == 200

    # Edit one suggestion
    sug_id = suggestions[0]["id"]
    edit_res = client.put(f"/api/forms/suggestions/{sug_id}", json={
        "review_status": "edited",
        "edited_value": "Alexander J. Morgan, PhD"
    })
    assert edit_res.status_code == 200

    # Test export as JSON
    export_json_res = client.get(f"/api/forms/sessions/{session_id}/export?format=json")
    assert export_json_res.status_code == 200
    export_data = export_json_res.get_json()
    assert export_data["form_id"] == session_id
    assert len(export_data["fields"]) == 6

    # Test export as CSV
    export_csv_res = client.get(f"/api/forms/sessions/{session_id}/export?format=csv")
    assert export_csv_res.status_code == 200
    assert b"Field Label,Field Key" in export_csv_res.data


def test_analytics_and_history(client):
    # Process a form
    client.post("/api/profile/seed-sample")
    analyze_res = client.post("/api/forms/analyze", json={
        "form_name": "Scholarship Form",
        "raw_input": "Full Name\nEmail Address"
    })
    session_id = analyze_res.get_json()["session_id"]
    client.get(f"/api/forms/sessions/{session_id}/export?format=json")

    # Check analytics
    analytics_res = client.get("/api/analytics")
    assert analytics_res.status_code == 200
    metrics = analytics_res.get_json()["metrics"]
    assert metrics["total_forms_processed"] >= 1
    assert metrics["total_saved_profile_fields"] > 0
    assert metrics["time_saved_seconds"] >= 0

    # Check history
    history_res = client.get("/api/history")
    assert history_res.status_code == 200
    hist = history_res.get_json()["history"]
    assert len(hist) >= 1
    hist_id = hist[0]["id"]

    # Delete history item
    del_hist = client.delete(f"/api/history/{hist_id}")
    assert del_hist.status_code == 200


def test_settings_and_privacy_reset(client):
    # Get settings
    settings_res = client.get("/api/settings")
    assert settings_res.status_code == 200

    # Update settings
    put_res = client.put("/api/settings", json={
        "confidence_threshold_high": 0.85,
        "time_saved_per_field_seconds": 60,
        "theme": "light"
    })
    assert put_res.status_code == 200

    # Reset all data (privacy safeguard)
    reset_res = client.post("/api/settings/reset-all")
    assert reset_res.status_code == 200

    # Verify profile is now empty
    get_res = client.get("/api/profile")
    profile = get_res.get_json()["profile"]
    assert profile["full_name"] == ""
    assert profile["skills"] == []
