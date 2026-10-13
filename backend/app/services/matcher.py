"""
Form Field Matching Service for OptMetrics.
Implements the hybrid matching pipeline:
1. Exact field-name matching.
2. Synonym, alias, and keyword matching.
3. Semantic similarity via sentence-transformers (or TF-IDF n-grams fallback).
4. Dropdown option matching.
5. Answer formatting and validation against expected field types.
6. Confidence scoring and transparent explanation generation.
"""

import json
from .nlp_engine import (
    clean_form_label,
    compute_tfidf_similarity,
    compute_semantic_embedding_similarity,
    compute_string_similarity,
    PROFILE_FIELD_ALIASES
)
from ..utils.validators import validate_field_value

# Profile field human-readable titles
PROFILE_FIELD_TITLES = {
    "full_name": "Full Name",
    "email": "Email Address",
    "phone": "Phone Number",
    "address": "Residential Address",
    "date_of_birth": "Date of Birth",
    "college": "College / University",
    "degree": "Degree / Qualification",
    "branch": "Branch / Major",
    "graduation_year": "Graduation Year",
    "skills": "Technical Skills",
    "projects": "Projects",
    "work_experience": "Work Experience",
    "certifications": "Certifications"
}


def format_field_value_for_form(raw_value):
    """Format raw database values (lists/JSON) into appropriate form string."""
    if raw_value is None:
        return ""
    if isinstance(raw_value, list):
        return ", ".join(str(item) for item in raw_value if item)
    if isinstance(raw_value, str):
        val_str = raw_value.strip()
        if (val_str.startswith('[') and val_str.endswith(']')) or (val_str.startswith('{') and val_str.endswith('}')):
            try:
                parsed = json.loads(val_str)
                if isinstance(parsed, list):
                    return ", ".join(str(item) for item in parsed if item)
            except Exception:
                pass
        return val_str
    return str(raw_value)


def match_dropdown_option(proposed_value, options):
    """
    If field has a fixed set of dropdown/radio options, find best matching option.
    """
    if not options or not proposed_value:
        return proposed_value

    clean_prop = str(proposed_value).strip().lower()
    for opt in options:
        opt_str = str(opt).strip()
        if opt_str.lower() == clean_prop:
            return opt_str

    # Partial / substring match
    for opt in options:
        opt_str = str(opt).strip().lower()
        if clean_prop in opt_str or opt_str in clean_prop:
            return str(opt).strip()

    # Best string similarity
    best_opt = None
    best_score = 0.0
    for opt in options:
        score = compute_string_similarity(clean_prop, str(opt).strip().lower())
        if score > best_score:
            best_score = score
            best_opt = str(opt).strip()

    if best_score >= 0.65:
        return best_opt

    return proposed_value


def match_field_to_profile(form_field, profile_dict, custom_fields=None, options=None):
    """
    Match a single form field against the user's profile and custom fields.
    Returns:
    {
        "matched_profile_field": str or None,
        "proposed_value": str,
        "confidence_score": float,
        "matching_method": str ('exact', 'synonym', 'semantic', 'custom', 'unmatched'),
        "explanation": str,
        "validation_status": str ('valid', 'warning', 'invalid'),
        "validation_message": str
    }
    """
    field_label = form_field.get("field_label", "")
    html_name = form_field.get("html_name", "")
    field_type = form_field.get("field_type", "text")
    clean_label = clean_form_label(field_label)
    clean_html_name = clean_form_label(html_name)

    best_match_key = None
    best_score = 0.0
    best_method = "unmatched"
    best_explanation = "No matching profile field found"

    # Step 1: Check Exact Matches
    for key, aliases in PROFILE_FIELD_ALIASES.items():
        key_clean = key.replace('_', ' ')
        if clean_label == key_clean or clean_html_name == key_clean or field_label.lower() == key.lower():
            best_match_key = key
            best_score = 1.0
            best_method = "exact"
            best_explanation = f"Exact field name match with '{PROFILE_FIELD_TITLES.get(key, key)}'"
            break
        for alias in aliases:
            if clean_label == alias or clean_html_name == alias:
                best_match_key = key
                best_score = 0.98
                best_method = "exact"
                best_explanation = f"Exact alias match for '{alias}'"
                break
        if best_match_key:
            break

    # Step 2: Check Custom Fields
    if not best_match_key and custom_fields:
        for cf in custom_fields:
            cf_key = cf.get("field_key", "")
            cf_label = cf.get("field_label", "")
            cf_clean = clean_form_label(cf_label)
            if clean_label == cf_clean or clean_html_name == cf_clean or cf_clean in clean_label:
                best_match_key = f"custom:{cf_key}"
                best_score = 0.95
                best_method = "custom"
                best_explanation = f"Matched custom profile field '{cf_label}'"
                break

    # Step 3: Check Synonym / Keyword Substring Matches
    if not best_match_key or best_score < 0.90:
        for key, aliases in PROFILE_FIELD_ALIASES.items():
            for alias in aliases:
                # Substring inclusion
                if alias in clean_label or clean_label in alias:
                    score = 0.88 if len(alias) > 4 else 0.80
                    if score > best_score:
                        best_match_key = key
                        best_score = score
                        best_method = "synonym"
                        best_explanation = f"Matched keyword synonym '{alias}' in '{field_label}'"

    # Step 4: Semantic and Vector Matching (sentence-transformers or TF-IDF n-grams)
    if not best_match_key or best_score < 0.85:
        candidate_fields = list(PROFILE_FIELD_ALIASES.keys())
        for key in candidate_fields:
            title = PROFILE_FIELD_TITLES.get(key, key)
            aliases = PROFILE_FIELD_ALIASES.get(key, [])
            all_target_phrases = [title] + aliases

            for phrase in all_target_phrases:
                # Try sentence-transformers embedding first
                emb_sim = compute_semantic_embedding_similarity(clean_label, phrase)
                if emb_sim is not None:
                    sim = emb_sim
                    used_method = "semantic (transformer)"
                else:
                    sim = compute_tfidf_similarity(clean_label, phrase)
                    used_method = "semantic (n-gram)"

                if sim > best_score and sim >= 0.52:
                    best_score = round(sim, 2)
                    best_match_key = key
                    best_method = "semantic"
                    best_explanation = (
                        f"Semantic similarity ({int(sim * 100)}%) between "
                        f"'{field_label}' and '{title}' using {used_method}"
                    )

    # Resolve Proposed Value
    proposed_value = ""
    if best_match_key:
        if best_match_key.startswith("custom:"):
            target_ck = best_match_key.split("custom:", 1)[1]
            for cf in (custom_fields or []):
                if cf.get("field_key") == target_ck:
                    proposed_value = cf.get("field_value", "")
                    break
        else:
            raw_val = profile_dict.get(best_match_key)
            proposed_value = format_field_value_for_form(raw_val)

    # Check dropdown options if supplied
    if options and proposed_value:
        proposed_value = match_dropdown_option(proposed_value, options)

    # Validate value against expected field type
    is_valid, val_status, val_msg = validate_field_value(field_type, proposed_value)

    # Adjust confidence if value is missing from profile
    if best_match_key and not proposed_value:
        best_explanation += " (Note: Profile field is currently empty)"
        best_score = max(0.0, best_score - 0.25)
        val_status = "warning"
        val_msg = "Field matched, but no saved data in profile"

    return {
        "matched_profile_field": best_match_key,
        "proposed_value": proposed_value,
        "confidence_score": round(best_score, 2),
        "matching_method": best_method,
        "explanation": best_explanation,
        "validation_status": val_status,
        "validation_message": val_msg
    }


def match_form_fields(detected_fields, profile_data, custom_fields=None):
    """
    Batch process form fields against user profile.
    Returns list of match result dictionaries.
    """
    results = []
    for field in detected_fields:
        opts = field.get("original_options")
        if isinstance(opts, str) and opts:
            try:
                opts = json.loads(opts)
            except Exception:
                opts = [o.strip() for o in opts.split(",") if o.strip()]

        match_res = match_field_to_profile(field, profile_data, custom_fields, options=opts)
        match_res["field_id"] = field.get("id")
        match_res["field_key"] = field.get("field_key")
        match_res["field_label"] = field.get("field_label")
        match_res["field_type"] = field.get("field_type", "text")
        match_res["html_name"] = field.get("html_name")
        match_res["html_id"] = field.get("html_id")
        match_res["is_required"] = field.get("is_required", 0)
        results.append(match_res)

    return results
