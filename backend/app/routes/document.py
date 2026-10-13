"""
Document upload and resume parsing routes for OptMetrics.
Provides secure upload, document text parsing, user review, and profile updating.
"""

import os
import json
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from ..models.database import get_db_connection, row_to_dict
from ..services.doc_parser import parse_uploaded_file, allowed_file, MAX_FILE_SIZE_BYTES

document_bp = Blueprint("document", __name__, url_prefix="/api/documents")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@document_bp.route("", methods=["GET"])
def list_documents():
    """List all previously uploaded and parsed documents."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, original_name, file_type, file_size, status, created_at FROM documents ORDER BY id DESC")
    docs = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({"documents": docs}), 200


@document_bp.route("/upload", methods=["POST"])
def upload_document():
    """
    Handle document upload, perform validation, parse text, and extract info.
    Returns extracted information for user review.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for upload"}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "error": "Unsupported file format. Please upload a PDF (.pdf) or Word (.docx) document."
        }), 400

    # Read content length or check size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:
        return jsonify({"error": "File size exceeds maximum limit of 10 MB."}), 400

    # Generate secure, unique filename to prevent path traversal
    original_name = secure_filename(file.filename) or "document"
    ext = original_name.rsplit('.', 1)[-1].lower()
    unique_filename = f"{uuid.uuid4().hex}_{original_name}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_filename)

    try:
        file.save(save_path)
    except Exception as e:
        return jsonify({"error": f"Failed to save uploaded file: {str(e)}"}), 500

    # Parse document
    try:
        parsed_data = parse_uploaded_file(save_path, original_name)
    except ValueError as ve:
        # Graceful handling of parsing errors
        return jsonify({
            "error": str(ve),
            "filename": original_name
        }), 422
    except Exception as e:
        return jsonify({
            "error": f"An error occurred while parsing the document: {str(e)}",
            "filename": original_name
        }), 500

    # Save to database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents (filename, original_name, file_type, file_size, extracted_data_json, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (unique_filename, original_name, ext, file_size, json.dumps(parsed_data), 'parsed'))
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Document parsed successfully",
        "document_id": doc_id,
        "filename": original_name,
        "extracted_data": parsed_data
    }), 201


@document_bp.route("/apply-to-profile", methods=["POST"])
def apply_to_profile():
    """
    Apply user-reviewed and approved extracted values to their profile.
    Only updates fields the user confirmed.
    """
    data = request.get_json() or {}
    approved_fields = data.get("approved_fields", {})

    if not approved_fields:
        return jsonify({"error": "No approved fields provided"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch current profile
    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    current_profile = row_to_dict(cursor.fetchone())

    # Build updates
    updates = {}
    for key in ["full_name", "email", "phone", "college", "degree", "branch", "graduation_year"]:
        if key in approved_fields and approved_fields[key]:
            updates[key] = approved_fields[key]
        else:
            updates[key] = current_profile.get(key)

    # For list fields (skills, projects, work_experience, certifications)
    for list_key in ["skills", "projects", "work_experience", "certifications"]:
        if list_key in approved_fields and approved_fields[list_key] is not None:
            val = approved_fields[list_key]
            if isinstance(val, list):
                updates[list_key] = json.dumps(val)
            else:
                updates[list_key] = json.dumps([v.strip() for v in str(val).split(",") if v.strip()])
        else:
            updates[list_key] = current_profile.get(list_key) or "[]"

    cursor.execute("""
        UPDATE user_profile
        SET full_name = :full_name, email = :email, phone = :phone,
            college = :college, degree = :degree, branch = :branch,
            graduation_year = :graduation_year, skills = :skills,
            projects = :projects, work_experience = :work_experience,
            certifications = :certifications, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, updates)

    conn.commit()
    conn.close()

    return jsonify({"message": "Profile updated with approved document information"}), 200


@document_bp.route("/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    """Delete a document record and file from disk."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()

    if row:
        file_path = os.path.join(UPLOAD_FOLDER, row["filename"])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()

    conn.close()
    return jsonify({"message": "Document deleted successfully"}), 200
