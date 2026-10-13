"""
Automated unit tests for OptMetrics Form Field Matching and Scoring.
Tests differently worded labels, exact matches, synonyms, semantic fallbacks,
confidence thresholds, validation, and dropdown selection.
"""

import pytest
from app.services.matcher import match_field_to_profile, match_form_fields
from app.services.nlp_engine import clean_form_label


@pytest.fixture
def sample_profile():
    return {
        "full_name": "Jordan Taylor",
        "email": "jordan.taylor@example.edu",
        "phone": "+1-555-0199",
        "college": "State Technical University",
        "degree": "Bachelor of Technology",
        "branch": "Computer Science and Engineering",
        "graduation_year": "2026",
        "skills": ["Python", "React", "Docker", "Machine Learning"],
        "projects": ["OptMetrics AI Autofill", "Distributed Cache System"],
        "work_experience": ["Software Intern at Alpha Labs"],
        "certifications": ["AWS Certified Developer"]
    }


def test_clean_form_label():
    assert clean_form_label("Please enter your Full Name*:") == "full name"
    assert clean_form_label("What is your Expected Graduation Year?") == "expected graduation year"
    assert clean_form_label("Enter your official email id") == "official email id"


def test_exact_and_synonym_matches(sample_profile):
    # Institution Name -> saved college
    res1 = match_field_to_profile({"field_label": "Institution Name", "field_type": "text"}, sample_profile)
    assert res1["matched_profile_field"] == "college"
    assert res1["proposed_value"] == "State Technical University"
    assert res1["confidence_score"] >= 0.85

    # University/College -> saved college
    res2 = match_field_to_profile({"field_label": "University/College", "field_type": "text"}, sample_profile)
    assert res2["matched_profile_field"] == "college"
    assert res2["confidence_score"] >= 0.85

    # Current Degree -> saved degree
    res3 = match_field_to_profile({"field_label": "Current Degree", "field_type": "text"}, sample_profile)
    assert res3["matched_profile_field"] == "degree"
    assert res3["proposed_value"] == "Bachelor of Technology"

    # Technical Skills -> saved skills
    res4 = match_field_to_profile({"field_label": "Technical Skills", "field_type": "textarea"}, sample_profile)
    assert res4["matched_profile_field"] == "skills"
    assert "Python" in res4["proposed_value"]

    # Expected Graduation Year -> saved graduation year
    res5 = match_field_to_profile({"field_label": "Expected Graduation Year", "field_type": "year"}, sample_profile)
    assert res5["matched_profile_field"] == "graduation_year"
    assert res5["proposed_value"] == "2026"
    assert res5["confidence_score"] >= 0.85


def test_differently_worded_and_ambiguous_labels(sample_profile):
    # Candidate Full Name
    res1 = match_field_to_profile({"field_label": "Candidate Full Name", "field_type": "text"}, sample_profile)
    assert res1["matched_profile_field"] == "full_name"
    assert res1["proposed_value"] == "Jordan Taylor"

    # Mobile Contact Number
    res2 = match_field_to_profile({"field_label": "Mobile Contact Number", "field_type": "phone"}, sample_profile)
    assert res2["matched_profile_field"] == "phone"
    assert res2["proposed_value"] == "+1-555-0199"

    # Completely unmatchable label
    res_unknown = match_field_to_profile({"field_label": "Favorite Ice Cream Flavor", "field_type": "text"}, sample_profile)
    assert res_unknown["confidence_score"] < 0.40 or res_unknown["matching_method"] == "unmatched"


def test_missing_profile_information():
    empty_profile = {
        "full_name": "",
        "email": "",
        "college": "",
        "graduation_year": ""
    }
    res = match_field_to_profile({"field_label": "College Name", "field_type": "text"}, empty_profile)
    assert res["matched_profile_field"] == "college"
    assert res["proposed_value"] == ""
    assert res["validation_status"] == "warning"
    # Should reduce confidence when field is empty in profile
    assert res["confidence_score"] < 0.80


def test_dropdown_option_selection(sample_profile):
    # Dropdown with years
    dropdown_field = {
        "field_label": "Select Graduation Year",
        "field_type": "select",
        "original_options": ["2024", "2025", "2026", "2027", "2028"]
    }
    res = match_field_to_profile(dropdown_field, sample_profile, options=dropdown_field["original_options"])
    assert res["proposed_value"] == "2026"


def test_custom_fields_matching(sample_profile):
    custom_fields = [
        {"field_key": "github_username", "field_label": "GitHub Handle", "field_value": "jordantaylor-dev"}
    ]
    res = match_field_to_profile(
        {"field_label": "GitHub Handle", "field_type": "text"},
        sample_profile,
        custom_fields=custom_fields
    )
    assert res["matched_profile_field"] == "custom:github_username"
    assert res["proposed_value"] == "jordantaylor-dev"
    assert res["confidence_score"] >= 0.90
