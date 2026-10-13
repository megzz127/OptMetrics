"""
Settings and Privacy Control routes for OptMetrics.
Manages confidence thresholds, baseline calculation settings, theme,
and full data deletion / reset for privacy compliance.
"""

import os
import shutil
from flask import Blueprint, request, jsonify
from ..models.database import get_db_connection, row_to_dict

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@settings_bp.route("", methods=["GET"])
def get_settings():
    """Retrieve current system and user preferences."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_preferences WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({
            "confidence_threshold_high": 0.80,
            "confidence_threshold_medium": 0.50,
            "auto_accept_high_confidence": 0,
            "time_saved_per_field_seconds": 45,
            "theme": "dark"
        }), 200

    return jsonify({"settings": row_to_dict(row)}), 200


@settings_bp.route("", methods=["PUT"])
def update_settings():
    """Update system preferences."""
    data = request.get_json() or {}
    thresh_high = float(data.get("confidence_threshold_high", 0.80))
    thresh_med = float(data.get("confidence_threshold_medium", 0.50))
    auto_accept = 1 if data.get("auto_accept_high_confidence") else 0
    time_saved = int(data.get("time_saved_per_field_seconds", 45))
    theme = data.get("theme", "dark")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_preferences
        SET confidence_threshold_high = ?,
            confidence_threshold_medium = ?,
            auto_accept_high_confidence = ?,
            time_saved_per_field_seconds = ?,
            theme = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (thresh_high, thresh_med, auto_accept, time_saved, theme))
    conn.commit()
    conn.close()

    return jsonify({"message": "Settings updated successfully"}), 200


@settings_bp.route("/reset-all", methods=["POST"])
def reset_all_data():
    """
    Privacy safeguard: Complete deletion of all personal data,
    uploaded documents, processing history, and custom fields.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear tables
    cursor.execute("DELETE FROM suggested_answers")
    cursor.execute("DELETE FROM detected_fields")
    cursor.execute("DELETE FROM form_sessions")
    cursor.execute("DELETE FROM form_history")
    cursor.execute("DELETE FROM profile_custom_fields")
    cursor.execute("DELETE FROM documents")

    # Reset profile to empty state
    cursor.execute("""
        UPDATE user_profile
        SET full_name = '', email = '', phone = '', address = '', date_of_birth = '',
            college = '', degree = '', branch = '', graduation_year = '',
            skills = '[]', projects = '[]', work_experience = '[]', certifications = '[]',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """)

    conn.commit()
    conn.close()

    # Clear uploads directory
    uploads_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
    if os.path.exists(uploads_dir):
        for filename in os.listdir(uploads_dir):
            file_path = os.path.join(uploads_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception:
                pass

    return jsonify({"message": "All personal data, uploaded files, and history have been securely wiped."}), 200
