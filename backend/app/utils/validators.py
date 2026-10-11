"""
Validation utilities for form fields and extracted values.
"""

import re
from datetime import datetime


def validate_email(value):
    """Check if string is a valid email format."""
    if not value or not isinstance(value, str):
        return False
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, value.strip()))


def validate_phone(value):
    """Check if string has standard phone digits."""
    if not value or not isinstance(value, str):
        return False
    digits = re.sub(r'\D', '', value)
    return 7 <= len(digits) <= 15


def validate_year(value):
    """Check if string or number is a reasonable 4-digit graduation/calendar year."""
    if not value:
        return False
    val_str = str(value).strip()
    if re.match(r'^(19|20)\d{2}$', val_str):
        year = int(val_str)
        return 1950 <= year <= 2040
    return False


def validate_date(value):
    """Check if string is a valid parseable date."""
    if not value or not isinstance(value, str):
        return False
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def validate_url(value):
    """Check if string is a valid URL or web profile."""
    if not value or not isinstance(value, str):
        return False
    pattern = r'^(https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    return bool(re.match(pattern, value.strip()))


def validate_field_value(field_type, value):
    """
    Validate an answer value against the expected field type.
    Returns: (is_valid, validation_status, message)
      status: 'valid' | 'warning' | 'invalid'
    """
    if not value:
        return True, "valid", "Empty or not specified"

    val_str = str(value).strip()
    t = (field_type or "text").lower()

    if t in ["email", "e-mail"]:
        if validate_email(val_str):
            return True, "valid", "Valid email format"
        return False, "invalid", "Value does not match expected email format"

    elif t in ["phone", "tel", "mobile", "contact_number"]:
        if validate_phone(val_str):
            return True, "valid", "Valid phone number format"
        return False, "warning", "Phone format may be incomplete or invalid"

    elif t in ["year", "grad_year", "graduation_year"]:
        if validate_year(val_str):
            return True, "valid", "Valid 4-digit year"
        return False, "warning", "Expected a 4-digit year (e.g. 2025)"

    elif t in ["date", "dob", "birth_date"]:
        if validate_date(val_str):
            return True, "valid", "Valid date format"
        return False, "warning", "Expected a date format (YYYY-MM-DD or DD/MM/YYYY)"

    elif t in ["url", "website", "linkedin", "github", "portfolio"]:
        if validate_url(val_str):
            return True, "valid", "Valid web URL"
        return False, "warning", "Value is not a standard web URL"

    elif t in ["number", "numeric", "integer", "gpa", "percentage"]:
        # Allow numbers, floats, percentages
        clean = val_str.replace('%', '').strip()
        try:
            float(clean)
            return True, "valid", "Valid numeric value"
        except ValueError:
            return False, "warning", "Expected a numeric value"

    return True, "valid", "Valid"
