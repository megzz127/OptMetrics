"""
Form Analyzer and Review Suggestions routes for OptMetrics.
Processes pasted questions, uploaded forms, extension payloads,
matches fields to profile, manages review workflow, and exports approved answers.
"""

import json
import re
from flask import Blueprint, request, jsonify, Response
from ..models.database import get_db_connection, row_to_dict
from ..services.matcher import match_form_fields
from ..utils.exporters import export_answers_to_json, export_answers_to_csv

analyzer_bp = Blueprint("analyzer", __name__, url_prefix="/api/forms")


def parse_pasted_questions_to_fields(raw_text):
    """
    Parse a multiline pasted block of form questions or field labels into structured field dicts.
    Handles numbered lists, bullet points, colons, question marks, and inferred types.
    """
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    fields = []

    for idx, line in enumerate(lines, 1):
        # Strip leading numbers or bullets like '1. ', '• ', '- ', 'Q1: '
        cleaned = re.sub(r'^(?:(?:\d+[\.\)]|[•\-\*]|q\d+[:\.\)])\s*)', '', line, flags=re.IGNORECASE).strip()
        if not cleaned:
            continue

        # Invert type heuristics based on text keywords
        lower = cleaned.lower()
        field_type = "text"
        options = None

        if any(w in lower for w in ["email", "e-mail"]):
            field_type = "email"
        elif any(w in lower for w in ["phone", "mobile", "contact no", "telephone"]):
            field_type = "phone"
        elif any(w in lower for w in ["graduation year", "passing year", "batch", "passout year"]):
            field_type = "year"
        elif any(w in lower for w in ["date of birth", "dob", "birth date", "birthday"]):
            field_type = "date"
        elif any(w in lower for w in ["linkedin", "github", "website", "portfolio", "url"]):
            field_type = "url"
        elif any(w in lower for w in ["gpa", "cgpa", "percentage", "marks"]):
            field_type = "number"
        elif any(w in lower for w in ["experience", "projects", "address", "statement", "cover letter"]):
            field_type = "textarea"

        # Check if options are mentioned in parentheses: e.g. "(Yes/No)" or "(B.Tech, M.Tech, BCA)"
        opt_match = re.search(r'\(([^)]+)\)$', cleaned)
        if opt_match and ('/' in opt_match.group(1) or ',' in opt_match.group(1)):
            raw_opts = opt_match.group(1)
            options = [o.strip() for o in re.split(r'[/,]', raw_opts) if o.strip()]
            cleaned = re.sub(r'\s*\([^)]+\)$', '', cleaned).strip()

        fields.append({
            "field_key": f"field_{idx}",
            "field_label": cleaned,
            "field_type": field_type,
            "html_name": f"input_{idx}",
            "html_id": f"field_id_{idx}",
            "is_required": 1 if '*' in line else 0,
            "original_options": options
        })

    return fields


@analyzer_bp.route("/sample-form", methods=["GET"])
def get_sample_form():
    """Return a pre-configured sample form with common application questions for quick testing."""
    sample = {
        "form_name": "Tech Corp Internship Application Form",
        "description": "Realistic standard internship form with varied labels and field types",
        "fields": [
            {"field_label": "Applicant Full Name", "field_type": "text", "is_required": 1},
            {"field_label": "Official Email ID", "field_type": "email", "is_required": 1},
            {"field_label": "Contact Number", "field_type": "phone", "is_required": 1},
            {"field_label": "University / Institution Name", "field_type": "text", "is_required": 1},
            {"field_label": "Current Degree Program", "field_type": "text", "is_required": 1},
            {"field_label": "Engineering Branch / Major", "field_type": "text", "is_required": 1},
            {"field_label": "Expected Graduation Year", "field_type": "year", "is_required": 1},
            {"field_label": "Technical Skills & Competencies", "field_type": "textarea", "is_required": 0},
            {"field_label": "Relevant Project Experience", "field_type": "textarea", "is_required": 0},
            {"field_label": "Past Work Experience / Internships", "field_type": "textarea", "is_required": 0},
            {"field_label": "Certifications & Credentials", "field_type": "text", "is_required": 0},
            {"field_label": "Residential Address", "field_type": "textarea", "is_required": 0},
            {"field_label": "Date of Birth (YYYY-MM-DD)", "field_type": "date", "is_required": 0},
            {"field_label": "LinkedIn Profile", "field_type": "url", "is_required": 0},
            {"field_label": "GitHub Portfolio", "field_type": "url", "is_required": 0}
        ]
    }
    return jsonify(sample), 200


@analyzer_bp.route("/analyze", methods=["POST"])
def analyze_form():
    """
    Analyze form fields, match against user profile, and create a review session.
    """
    data = request.get_json() or {}
    form_name = data.get("form_name", "Application Form").strip() or "Application Form"
    source = data.get("source", "pasted")
    raw_input = data.get("raw_input", "")
    input_fields = data.get("fields", [])

    if not input_fields and raw_input:
        input_fields = parse_pasted_questions_to_fields(raw_input)

    if not input_fields:
        return jsonify({"error": "No form fields detected. Please provide field labels or questions."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch user profile
    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    profile_row = cursor.fetchone()
    profile_dict = row_to_dict(profile_row) if profile_row else {}

    # Fetch custom fields
    cursor.execute("SELECT * FROM profile_custom_fields WHERE profile_id = 1")
    custom_rows = cursor.fetchall()
    custom_fields = [row_to_dict(r) for r in custom_rows]

    # Fetch user preferences
    cursor.execute("SELECT * FROM user_preferences WHERE id = 1")
    pref_row = cursor.fetchone()
    pref = row_to_dict(pref_row) if pref_row else {}
    thresh_high = pref.get("confidence_threshold_high", 0.80)
    auto_accept = pref.get("auto_accept_high_confidence", 0)

    # Perform field matching
    matches = match_form_fields(input_fields, profile_dict, custom_fields)

    total_fields = len(matches)
    matched_count = sum(1 for m in matches if m.get("confidence_score", 0) >= 0.50)
    review_needed = sum(1 for m in matches if m.get("confidence_score", 0) < thresh_high)

    # Insert form session
    cursor.execute("""
        INSERT INTO form_sessions (form_name, source, raw_input, total_fields, matched_fields, review_needed, status)
        VALUES (?, ?, ?, ?, ?, ?, 'analyzed')
    """, (form_name, source, raw_input, total_fields, matched_count, review_needed))
    session_id = cursor.lastrowid

    # Insert detected fields and suggestions
    enriched_suggestions = []
    for m in matches:
        opts_json = json.dumps(m.get("original_options")) if m.get("original_options") else None
        cursor.execute("""
            INSERT INTO detected_fields (session_id, field_key, field_label, field_type, original_options, html_name, html_id, is_required)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            m.get("field_key", "field"),
            m.get("field_label", ""),
            m.get("field_type", "text"),
            opts_json,
            m.get("html_name", ""),
            m.get("html_id", ""),
            m.get("is_required", 0)
        ))
        detected_field_id = cursor.lastrowid

        conf = m.get("confidence_score", 0.0)
        initial_status = "accepted" if (auto_accept and conf >= thresh_high) else "pending"

        cursor.execute("""
            INSERT INTO suggested_answers (
                session_id, detected_field_id, matched_profile_field, proposed_value,
                confidence_score, matching_method, explanation, review_status, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            detected_field_id,
            m.get("matched_profile_field"),
            m.get("proposed_value", ""),
            conf,
            m.get("matching_method", "unmatched"),
            m.get("explanation", ""),
            initial_status,
            m.get("validation_status", "valid")
        ))
        sug_id = cursor.lastrowid

        m["id"] = sug_id
        m["detected_field_id"] = detected_field_id
        m["session_id"] = session_id
        m["review_status"] = initial_status
        enriched_suggestions.append(m)

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Form analyzed successfully",
        "session_id": session_id,
        "form_name": form_name,
        "total_fields": total_fields,
        "matched_fields": matched_count,
        "review_needed": review_needed,
        "suggestions": enriched_suggestions
    }), 201


@analyzer_bp.route("/sessions/<int:session_id>", methods=["GET"])
def get_session(session_id):
    """Retrieve all fields and suggestions for a form session."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM form_sessions WHERE id = ?", (session_id,))
    session_row = cursor.fetchone()
    if not session_row:
        conn.close()
        return jsonify({"error": "Form session not found"}), 404

    session_data = row_to_dict(session_row)

    query = """
        SELECT
            s.id,
            s.session_id,
            s.detected_field_id,
            s.matched_profile_field,
            s.proposed_value,
            s.confidence_score,
            s.matching_method,
            s.explanation,
            s.review_status,
            s.edited_value,
            s.validation_status,
            d.field_key,
            d.field_label,
            d.field_type,
            d.html_name,
            d.html_id,
            d.is_required,
            d.original_options
        FROM suggested_answers s
        JOIN detected_fields d ON s.detected_field_id = d.id
        WHERE s.session_id = ?
        ORDER BY d.id ASC
    """
    cursor.execute(query, (session_id,))
    rows = cursor.fetchall()
    conn.close()

    suggestions = [row_to_dict(r) for r in rows]

    return jsonify({
        "session": session_data,
        "suggestions": suggestions
    }), 200


@analyzer_bp.route("/suggestions/<int:suggestion_id>", methods=["PUT"])
def update_suggestion(suggestion_id):
    """
    Update a single suggestion's review status (accepted, rejected, edited)
    and optional user-edited value.
    """
    data = request.get_json() or {}
    review_status = data.get("review_status")
    edited_value = data.get("edited_value")

    allowed_statuses = ["pending", "accepted", "rejected", "edited"]
    if review_status and review_status not in allowed_statuses:
        return jsonify({"error": f"Invalid review_status. Allowed: {allowed_statuses}"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM suggested_answers WHERE id = ?", (suggestion_id,))
    current = cursor.fetchone()
    if not current:
        conn.close()
        return jsonify({"error": "Suggestion not found"}), 404

    new_status = review_status or current["review_status"]
    new_edited = edited_value if edited_value is not None else current["edited_value"]

    cursor.execute("""
        UPDATE suggested_answers
        SET review_status = ?, edited_value = ?
        WHERE id = ?
    """, (new_status, new_edited, suggestion_id))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Suggestion updated",
        "suggestion_id": suggestion_id,
        "review_status": new_status,
        "edited_value": new_edited
    }), 200


@analyzer_bp.route("/sessions/<int:session_id>/approve-all", methods=["POST"])
def approve_all_high_confidence(session_id):
    """Approve all high-confidence suggestions in this session."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get user threshold
    cursor.execute("SELECT confidence_threshold_high FROM user_preferences WHERE id = 1")
    pref = cursor.fetchone()
    thresh = pref["confidence_threshold_high"] if pref else 0.80

    cursor.execute("""
        UPDATE suggested_answers
        SET review_status = 'accepted'
        WHERE session_id = ?
          AND confidence_score >= ?
          AND review_status != 'rejected'
    """, (session_id, thresh))

    updated_count = cursor.rowcount
    conn.commit()
    conn.close()

    return jsonify({
        "message": f"Approved {updated_count} high-confidence suggestions",
        "count": updated_count
    }), 200


@analyzer_bp.route("/sessions/<int:session_id>/export", methods=["GET"])
def export_session_answers(session_id):
    """
    Export approved answers for this form as JSON or CSV.
    Logs form completion in form_history.
    """
    export_format = request.args.get("format", "json").lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM form_sessions WHERE id = ?", (session_id,))
    session_row = cursor.fetchone()
    if not session_row:
        conn.close()
        return jsonify({"error": "Form session not found"}), 404

    session_data = row_to_dict(session_row)

    query = """
        SELECT
            s.*,
            d.field_key,
            d.field_label,
            d.field_type,
            d.html_name,
            d.html_id,
            d.is_required
        FROM suggested_answers s
        JOIN detected_fields d ON s.detected_field_id = d.id
        WHERE s.session_id = ?
        ORDER BY d.id ASC
    """
    cursor.execute(query, (session_id,))
    suggestions = [row_to_dict(r) for r in cursor.fetchall()]

    # Fetch preferences for time savings calculation
    cursor.execute("SELECT time_saved_per_field_seconds FROM user_preferences WHERE id = 1")
    pref_row = cursor.fetchone()
    time_per_field = pref_row["time_saved_per_field_seconds"] if pref_row else 45

    # Calculate stats for history entry
    total_fields = len(suggestions)
    matched_fields = sum(1 for s in suggestions if s.get("confidence_score", 0) >= 0.50)
    reviewed_fields = sum(1 for s in suggestions if s.get("review_status") in ["accepted", "edited"])
    corrected_fields = sum(1 for s in suggestions if s.get("review_status") == "edited")
    saved_seconds = reviewed_fields * time_per_field

    # Record or update in form_history
    cursor.execute("SELECT id FROM form_history WHERE session_id = ?", (session_id,))
    history_row = cursor.fetchone()
    if history_row:
        cursor.execute("""
            UPDATE form_history
            SET fields_detected = ?, fields_matched = ?, fields_reviewed = ?,
                fields_corrected = ?, completion_status = 'Exported', time_saved_seconds = ?
            WHERE session_id = ?
        """, (total_fields, matched_fields, reviewed_fields, corrected_fields, saved_seconds, session_id))
    else:
        cursor.execute("""
            INSERT INTO form_history (
                session_id, form_name, fields_detected, fields_matched,
                fields_reviewed, fields_corrected, completion_status, time_saved_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, 'Exported', ?)
        """, (session_id, session_data["form_name"], total_fields, matched_fields, reviewed_fields, corrected_fields, saved_seconds))

    cursor.execute("UPDATE form_sessions SET status = 'exported' WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

    if export_format == "csv":
        csv_data = export_answers_to_csv(session_data, suggestions)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=optmetrics_{session_id}_answers.csv"}
        )
    else:
        json_data = export_answers_to_json(session_data, suggestions)
        return Response(
            json_data,
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment;filename=optmetrics_{session_id}_answers.json"}
        )
