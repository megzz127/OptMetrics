"""
Export utilities for saving approved form answers to JSON or CSV.
"""

import csv
import json
import io


def export_answers_to_json(session_data, suggestions):
    """
    Format approved form answers as a structured JSON object.
    """
    result = {
        "form_id": session_data.get("id"),
        "form_name": session_data.get("form_name"),
        "exported_at": session_data.get("created_at"),
        "total_fields": len(suggestions),
        "fields": []
    }

    for item in suggestions:
        final_value = item.get("edited_value") if item.get("edited_value") is not None else item.get("proposed_value")
        result["fields"].append({
            "field_label": item.get("field_label"),
            "field_key": item.get("field_key"),
            "html_name": item.get("html_name"),
            "html_id": item.get("html_id"),
            "field_type": item.get("field_type"),
            "matched_profile_field": item.get("matched_profile_field"),
            "approved_value": final_value or "",
            "confidence_score": item.get("confidence_score"),
            "review_status": item.get("review_status")
        })

    return json.dumps(result, indent=2)


def export_answers_to_csv(session_data, suggestions):
    """
    Format approved form answers as CSV text.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Field Label",
        "Field Key",
        "HTML Name",
        "HTML ID",
        "Field Type",
        "Matched Profile Field",
        "Approved Answer",
        "Confidence Score",
        "Review Status"
    ])

    for item in suggestions:
        final_value = item.get("edited_value") if item.get("edited_value") is not None else item.get("proposed_value")
        writer.writerow([
            item.get("field_label", ""),
            item.get("field_key", ""),
            item.get("html_name", ""),
            item.get("html_id", ""),
            item.get("field_type", ""),
            item.get("matched_profile_field", ""),
            final_value or "",
            f"{float(item.get('confidence_score', 0) or 0):.2f}",
            item.get("review_status", "")
        ])

    return output.getvalue()
