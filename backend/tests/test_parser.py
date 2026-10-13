"""
Automated unit tests for document extraction and resume parser.
Tests text extraction, scanned PDF warning heuristics, and information extraction.
"""

import os
import pytest
from app.services.doc_parser import parse_document_text, parse_uploaded_file


def test_parse_sample_resume_text():
    sample_text = """
    Alex Morgan
    alex.morgan@example.com | +1 (555) 234-5678 | Austin, TX
    
    EDUCATION
    Apex Institute of Science and Technology
    Bachelor of Technology in Computer Science and Engineering
    Graduation Year: 2025
    
    SKILLS
    Python, JavaScript, React, Flask, SQL, Docker, Machine Learning
    
    EXPERIENCE
    Software Engineering Intern at CloudPulse Solutions (2024)
    Developed automated data ingestion pipelines.
    
    PROJECTS
    OptMetrics: Automated form completion system.
    SmartVision: Real-time object tracking with OpenCV.
    
    CERTIFICATIONS
    AWS Certified Cloud Practitioner
    """
    data = parse_document_text(sample_text)
    assert data["full_name"] == "Alex Morgan"
    assert data["email"] == "alex.morgan@example.com"
    assert "555" in data["phone"]
    assert "Apex Institute" in data["college"]
    assert "Bachelor of Technology" in data["degree"]
    assert "Computer Science" in data["branch"]
    assert data["graduation_year"] == "2025"
    assert "Python" in data["skills"]
    assert "React" in data["skills"]
    assert len(data["projects"]) > 0
    assert data["is_scanned_warning"] is False


def test_empty_or_scanned_document_handling():
    # Empty or very short text (< 30 chars)
    empty_data = parse_document_text("   ")
    assert empty_data["is_scanned_warning"] is True
    assert empty_data["warning_message"] is not None

    scanned_data = parse_document_text("Page 1")
    assert scanned_data["is_scanned_warning"] is True
    assert "scanned" in scanned_data["warning_message"].lower()


def test_invalid_file_handling():
    with pytest.raises(FileNotFoundError):
        parse_uploaded_file("non_existent_file_path.pdf", "non_existent_file_path.pdf")
