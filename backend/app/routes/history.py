"""
Form History management routes for OptMetrics.
Provides history listing, item deletion, and log clearing.
"""

from flask import Blueprint, jsonify
from ..models.database import get_db_connection, row_to_dict

history_bp = Blueprint("history", __name__, url_prefix="/api/history")


@history_bp.route("", methods=["GET"])
def get_history():
    """List all form processing history records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, session_id, form_name, date_processed,
               fields_detected, fields_matched, fields_reviewed,
               fields_corrected, completion_status, time_saved_seconds
        FROM form_history
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    history_list = [row_to_dict(r) for r in rows]
    return jsonify({"history": history_list}), 200


@history_bp.route("/<int:history_id>", methods=["DELETE"])
def delete_history_item(history_id):
    """Delete a single history entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM form_history WHERE id = ?", (history_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "History entry deleted"}), 200


@history_bp.route("/clear", methods=["DELETE"])
def clear_history():
    """Clear all form history records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM form_history")
    conn.commit()
    conn.close()
    return jsonify({"message": "Form history cleared successfully"}), 200
