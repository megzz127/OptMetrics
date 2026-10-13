"""
Profile management routes for OptMetrics.
Allows viewing, updating, creating custom fields, and populating sample profiles.
"""

import json
from flask import Blueprint, request, jsonify
from ..models.database import get_db_connection, row_to_dict

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@profile_bp.route("", methods=["GET"])
def get_profile():
    """Retrieve the user's primary profile and custom fields."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    profile_row = cursor.fetchone()

    cursor.execute("SELECT * FROM profile_custom_fields WHERE profile_id = 1 ORDER BY id ASC")
    custom_rows = cursor.fetchall()

    conn.close()

    if not profile_row:
        return jsonify({"error": "Profile not found"}), 404

    profile = row_to_dict(profile_row)

    # Decode JSON fields
    for json_field in ["skills", "projects", "work_experience", "certifications"]:
        val = profile.get(json_field)
        if isinstance(val, str) and val:
            try:
                profile[json_field] = json.loads(val)
            except Exception:
                profile[json_field] = [s.strip() for s in val.split(",") if s.strip()]
        elif val is None:
            profile[json_field] = []

    custom_fields = [row_to_dict(r) for r in custom_rows]
    profile["custom_fields"] = custom_fields

    return jsonify({"profile": profile}), 200


@profile_bp.route("", methods=["PUT"])
def update_profile():
    """Update profile fields."""
    data = request.get_json() or {}
    conn = get_db_connection()
    cursor = conn.cursor()

    full_name = data.get("full_name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")
    address = data.get("address", "")
    date_of_birth = data.get("date_of_birth", "")
    college = data.get("college", "")
    degree = data.get("degree", "")
    branch = data.get("branch", "")
    graduation_year = data.get("graduation_year", "")

    skills = data.get("skills", [])
    if isinstance(skills, list):
        skills = json.dumps(skills)

    projects = data.get("projects", [])
    if isinstance(projects, list):
        projects = json.dumps(projects)

    work_experience = data.get("work_experience", [])
    if isinstance(work_experience, list):
        work_experience = json.dumps(work_experience)

    certifications = data.get("certifications", [])
    if isinstance(certifications, list):
        certifications = json.dumps(certifications)

    cursor.execute("""
        UPDATE user_profile
        SET full_name = ?, email = ?, phone = ?, address = ?, date_of_birth = ?,
            college = ?, degree = ?, branch = ?, graduation_year = ?,
            skills = ?, projects = ?, work_experience = ?, certifications = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (full_name, email, phone, address, date_of_birth,
          college, degree, branch, graduation_year,
          skills, projects, work_experience, certifications))

    conn.commit()
    conn.close()

    return jsonify({"message": "Profile updated successfully"}), 200


@profile_bp.route("/custom-field", methods=["POST"])
def add_custom_field():
    """Add a custom field to the profile."""
    data = request.get_json() or {}
    field_key = data.get("field_key", "").strip().lower().replace(" ", "_")
    field_label = data.get("field_label", "").strip()
    field_value = data.get("field_value", "").strip()
    field_type = data.get("field_type", "text").strip()

    if not field_label or not field_value:
        return jsonify({"error": "field_label and field_value are required"}), 400

    if not field_key:
        field_key = field_label.lower().replace(" ", "_")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO profile_custom_fields (profile_id, field_key, field_label, field_value, field_type)
        VALUES (1, ?, ?, ?, ?)
    """, (field_key, field_label, field_value, field_type))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Custom field added",
        "custom_field": {
            "id": new_id,
            "field_key": field_key,
            "field_label": field_label,
            "field_value": field_value,
            "field_type": field_type
        }
    }), 201


@profile_bp.route("/custom-field/<int:field_id>", methods=["DELETE"])
def delete_custom_field(field_id):
    """Delete a custom field."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profile_custom_fields WHERE id = ? AND profile_id = 1", (field_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Custom field deleted"}), 200


@profile_bp.route("/seed-sample", methods=["POST"])
def seed_sample_profile():
    """Load a fictional sample profile for quick testing and demonstration."""
    sample_data = {
        "full_name": "Alex J. Morgan",
        "email": "alex.morgan.tech@example.com",
        "phone": "+1 (555) 234-5678",
        "address": "124 Innovation Way, Tech District, Austin, TX 78701",
        "date_of_birth": "2002-05-18",
        "college": "Apex Institute of Science and Technology",
        "degree": "Bachelor of Technology",
        "branch": "Computer Science and Engineering",
        "graduation_year": "2025",
        "skills": json.dumps([
            "Python", "JavaScript", "React", "Flask", "SQL",
            "Machine Learning", "Docker", "Git", "REST APIs"
        ]),
        "projects": json.dumps([
            "OptMetrics: Automated intelligent form autofill platform using hybrid NLP",
            "SmartVision: Real-time object tracking system built with OpenCV and PyTorch",
            "CloudSync: Distributed asynchronous task queue engine in Python & Redis"
        ]),
        "work_experience": json.dumps([
            "Software Engineering Intern at CloudPulse Solutions (Summer 2024)",
            "Research Assistant at Apex AI Robotics Lab (2023 - 2024)"
        ]),
        "certifications": json.dumps([
            "AWS Certified Cloud Practitioner (2024)",
            "Deep Learning Specialization by Coursera (2023)"
        ])
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_profile
        SET full_name = :full_name, email = :email, phone = :phone,
            address = :address, date_of_birth = :date_of_birth,
            college = :college, degree = :degree, branch = :branch,
            graduation_year = :graduation_year, skills = :skills,
            projects = :projects, work_experience = :work_experience,
            certifications = :certifications, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, sample_data)

    # Insert sample custom fields
    cursor.execute("DELETE FROM profile_custom_fields WHERE profile_id = 1")
    cursor.execute("""
        INSERT INTO profile_custom_fields (profile_id, field_key, field_label, field_value, field_type)
        VALUES (1, 'linkedin_url', 'LinkedIn Profile', 'https://linkedin.com/in/alex-morgan-sample', 'url'),
               (1, 'github_url', 'GitHub Portfolio', 'https://github.com/alexmorgan-sample', 'url'),
               (1, 'cumulative_gpa', 'Cumulative GPA / Marks', '3.88 / 4.0', 'text')
    """)

    conn.commit()
    conn.close()

    return jsonify({"message": "Sample profile loaded successfully"}), 200
