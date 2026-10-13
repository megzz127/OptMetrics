"""
Productivity Analytics routes for OptMetrics.
Calculates real metrics directly from database records:
forms processed, fields matched, acceptance rate, fields corrected,
review requests, and time saved using configurable baseline.
"""

from flask import Blueprint, jsonify
from ..models.database import get_db_connection, row_to_dict

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.route("", methods=["GET"])
def get_analytics():
    """
    Calculate and return complete real-time productivity analytics.
    No hardcoded fake analytics.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. User preferences for baseline calculation
    cursor.execute("SELECT * FROM user_preferences WHERE id = 1")
    pref_row = cursor.fetchone()
    pref = row_to_dict(pref_row) if pref_row else {}
    time_saved_baseline_sec = pref.get("time_saved_per_field_seconds", 45)
    thresh_high = pref.get("confidence_threshold_high", 0.80)

    # 2. Total saved profile fields (non-empty fields)
    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    profile = row_to_dict(cursor.fetchone())
    profile_field_count = 0
    if profile:
        standard_keys = [
            "full_name", "email", "phone", "address", "date_of_birth",
            "college", "degree", "branch", "graduation_year"
        ]
        for k in standard_keys:
            if profile.get(k) and str(profile.get(k)).strip():
                profile_field_count += 1

        for list_k in ["skills", "projects", "work_experience", "certifications"]:
            raw = profile.get(list_k)
            if raw and raw not in ["[]", ""]:
                profile_field_count += 1

    # Count custom fields
    cursor.execute("SELECT COUNT(*) as count FROM profile_custom_fields WHERE profile_id = 1")
    custom_count = cursor.fetchone()["count"]
    total_saved_fields = profile_field_count + custom_count

    # 3. Total forms processed / sessions
    cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status = 'exported' THEN 1 ELSE 0 END) as completed FROM form_sessions")
    sess_row = cursor.fetchone()
    total_forms_processed = sess_row["total"] or 0
    forms_completed = sess_row["completed"] or 0

    # 4. Suggestions metrics (matched, accepted, rejected, edited, flagged)
    cursor.execute("""
        SELECT
            COUNT(*) as total_suggestions,
            SUM(CASE WHEN confidence_score >= 0.50 THEN 1 ELSE 0 END) as matched_fields,
            SUM(CASE WHEN review_status = 'accepted' THEN 1 ELSE 0 END) as accepted_fields,
            SUM(CASE WHEN review_status = 'edited' THEN 1 ELSE 0 END) as corrected_fields,
            SUM(CASE WHEN review_status = 'rejected' THEN 1 ELSE 0 END) as rejected_fields,
            SUM(CASE WHEN (confidence_score < ? OR review_status = 'pending') THEN 1 ELSE 0 END) as flagged_for_review
        FROM suggested_answers
    """, (thresh_high,))
    sug_row = cursor.fetchone()

    total_suggestions = sug_row["total_suggestions"] or 0
    matched_fields = sug_row["matched_fields"] or 0
    accepted_fields = sug_row["accepted_fields"] or 0
    corrected_fields = sug_row["corrected_fields"] or 0
    rejected_fields = sug_row["rejected_fields"] or 0
    flagged_for_review = sug_row["flagged_for_review"] or 0

    # 5. Match acceptance rate
    # Percentage of evaluated suggestions that were accepted or corrected into accepted state
    effective_accepted = accepted_fields + corrected_fields
    acceptance_rate = round((effective_accepted / total_suggestions * 100), 1) if total_suggestions > 0 else 0.0

    # 6. Estimated time saved calculation
    # Formula: (accepted + edited) * baseline seconds saved per autofilled/verified field
    total_seconds_saved = effective_accepted * time_saved_baseline_sec
    estimated_minutes_saved = round(total_seconds_saved / 60, 1)
    estimated_hours_saved = round(total_seconds_saved / 3600, 2)

    # 7. Recent activity list
    cursor.execute("""
        SELECT 'form' as type, form_name as title, created_at, status
        FROM form_sessions
        ORDER BY id DESC LIMIT 5
    """)
    recent_sessions = [row_to_dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT 'document' as type, original_name as title, created_at, status
        FROM documents
        ORDER BY id DESC LIMIT 5
    """)
    recent_docs = [row_to_dict(r) for r in cursor.fetchall()]

    # Combine and sort recent activity by timestamp
    recent_activity = sorted(recent_sessions + recent_docs, key=lambda x: x.get("created_at") or "", reverse=True)[:6]

    conn.close()

    return jsonify({
        "metrics": {
            "total_saved_profile_fields": total_saved_fields,
            "total_forms_processed": total_forms_processed,
            "forms_completed": forms_completed,
            "total_fields_matched": matched_fields,
            "fields_accepted": accepted_fields,
            "fields_corrected": corrected_fields,
            "fields_rejected": rejected_fields,
            "fields_flagged_for_review": flagged_for_review,
            "match_acceptance_rate": acceptance_rate,
            "time_saved_seconds": total_seconds_saved,
            "estimated_minutes_saved": estimated_minutes_saved,
            "estimated_hours_saved": estimated_hours_saved,
            "baseline_seconds_per_field": time_saved_baseline_sec,
            "baseline_note": f"Estimated based on a configurable baseline of {time_saved_baseline_sec} seconds saved per matched field vs manual entry"
        },
        "recent_activity": recent_activity
    }), 200
