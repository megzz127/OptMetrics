"""
Document extraction and resume parsing service using PyMuPDF and python-docx.
Extracts structured information: name, email, phone, education, skills, projects, experience.
Handles scanned PDFs, empty files, and malformed documents gracefully.
"""

import os
import re
import fitz  # PyMuPDF
import docx

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit

COMMON_SKILL_CATALOG = [
    "Python", "JavaScript", "TypeScript", "React", "Node.js", "Express", "Flask",
    "Django", "SQL", "PostgreSQL", "MySQL", "MongoDB", "SQLite", "HTML", "CSS",
    "Java", "C++", "C#", "C", "Go", "Rust", "Git", "GitHub", "Docker", "Kubernetes",
    "AWS", "Azure", "GCP", "Linux", "Machine Learning", "Deep Learning", "NLP",
    "PyTorch", "TensorFlow", "Scikit-Learn", "Pandas", "NumPy", "Rest API", "GraphQL",
    "Tailwind CSS", "Bootstrap", "Redux", "Data Structures", "Algorithms", "Agile", "Jira"
]

DEGREE_PATTERNS = [
    r'\b(?:Bachelor\s+of\s+Technology|B\.?Tech|B\.?E\.?|Bachelor\s+of\s+Engineering)\b',
    r'\b(?:Bachelor\s+of\s+Science|B\.?S\.?|B\.?Sc)\b',
    r'\b(?:Master\s+of\s+Technology|M\.?Tech|M\.?E\.?)\b',
    r'\b(?:Master\s+of\s+Science|M\.?S\.?|M\.?Sc)\b',
    r'\b(?:Master\s+of\s+Business\s+Administration|MBA)\b',
    r'\b(?:Bachelor\s+of\s+Arts|B\.?A\.?|Master\s+of\s+Arts|M\.?A\.?)\b',
    r'\b(?:Bachelor\s+of\s+Computer\s+Applications|BCA|Master\s+of\s+Computer\s+Applications|MCA)\b',
    r'\b(?:Ph\.?D|Doctor\s+of\s+Philosophy)\b'
]

BRANCH_PATTERNS = [
    r'Computer\s+Science(?:\s+and\s+Engineering)?',
    r'Information\s+Technology',
    r'Artificial\s+Intelligence(?:\s+and\s+Data\s+Science)?',
    r'Data\s+Science',
    r'Electrical(?:\s+and\s+Electronics)?\s+Engineering',
    r'Electronics\s+(?:and\s+Communication\s+)?Engineering',
    r'Mechanical\s+Engineering',
    r'Civil\s+Engineering',
    r'Software\s+Engineering',
    r'Business\s+Administration',
    r'Mathematics',
    r'Physics'
]


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_path):
    """
    Extract textual content from PDF using PyMuPDF.
    Detects if the PDF is scanned or image-only.
    """
    text_content = []
    doc = None
    try:
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text:
                text_content.append(text)
    except Exception as e:
        raise ValueError(f"Failed to read PDF document: {str(e)}")
    finally:
        if doc:
            doc.close()

    full_text = "\n".join(text_content).strip()
    return full_text


def extract_text_from_docx(file_path):
    """Extract text from DOCX paragraphs and tables."""
    try:
        doc = docx.Document(file_path)
        text_lines = []
        for p in doc.paragraphs:
            line = p.text.strip()
            if line:
                text_lines.append(line)
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text_lines.append(" | ".join(row_text))
        return "\n".join(text_lines).strip()
    except Exception as e:
        raise ValueError(f"Failed to read DOCX document: {str(e)}")


def parse_document_text(text):
    """
    Heuristic-based and regex-based information extraction from resume/CV text.
    Extracts name, email, phone, education, degree, branch, graduation year,
    skills, work experience, projects, and certifications.
    """
    data = {
        "full_name": "",
        "email": "",
        "phone": "",
        "address": "",
        "college": "",
        "degree": "",
        "branch": "",
        "graduation_year": "",
        "skills": [],
        "projects": [],
        "work_experience": [],
        "certifications": [],
        "custom_fields": [],
        "raw_text_length": len(text),
        "is_scanned_warning": False,
        "warning_message": None
    }

    if not text or len(text.strip()) < 30:
        data["is_scanned_warning"] = True
        data["warning_message"] = (
            "The uploaded document contains little to no extractable text. "
            "It may be a scanned image-based PDF. OptMetrics requires a text-based "
            "PDF or DOCX document or an OCR step to read scanned images."
        )
        return data

    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # 1. Extract Email
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    if email_match:
        data["email"] = email_match.group(0).strip()

    # 2. Extract Phone Number
    phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?\d{10,14}'
    phone_match = re.search(phone_pattern, text)
    if phone_match:
        data["phone"] = phone_match.group(0).strip()

    # 3. Extract Full Name
    # Usually in the first 5 non-empty lines, before email/phone/summary
    for line in lines[:6]:
        cleaned_line = re.sub(r'[^a-zA-Z\s]', '', line).strip()
        # Exclude headers like 'Resume', 'Curriculum Vitae', 'Page 1', etc.
        skip_words = ['resume', 'curriculum', 'vitae', 'cv', 'profile', 'contact', 'email', 'phone', 'portfolio']
        if any(w in cleaned_line.lower() for w in skip_words):
            continue
        words = cleaned_line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
            data["full_name"] = cleaned_line
            break

    # If full_name not found from capitalization, check line 1
    if not data["full_name"] and lines:
        first_line = re.sub(r'[^a-zA-Z\s]', '', lines[0]).strip()
        if 2 <= len(first_line.split()) <= 4:
            data["full_name"] = first_line

    # 4. Extract Degree
    for pattern in DEGREE_PATTERNS:
        deg_match = re.search(pattern, text, re.IGNORECASE)
        if deg_match:
            data["degree"] = deg_match.group(0).strip()
            break

    # 5. Extract Branch/Major
    for pattern in BRANCH_PATTERNS:
        branch_match = re.search(pattern, text, re.IGNORECASE)
        if branch_match:
            data["branch"] = branch_match.group(0).strip()
            break

    # 6. Extract College/University
    college_pattern = r'([A-Z][a-zA-Z\s,&]+(?:University|Institute\s+of\s+Technology|College|Institute|Academy|Polytechnic))'
    college_match = re.search(college_pattern, text)
    if college_match:
        data["college"] = college_match.group(1).strip()
    else:
        # Check line-by-line near degree
        for line in lines:
            if any(term in line.lower() for term in ['university', 'institute of technology', 'college of engineering', 'polytechnic']):
                data["college"] = line[:100].strip()
                break

    # 7. Extract Graduation Year
    # Look for 4-digit year 2010-2032
    year_matches = re.findall(r'\b(20(?:1[5-9]|2[0-9]|3[0-2]))\b', text)
    if year_matches:
        # Often the graduation year is the highest reasonable year mentioned
        data["graduation_year"] = str(max([int(y) for y in year_matches]))

    # 8. Extract Skills
    found_skills = set()
    # Check catalog items in text
    for skill in COMMON_SKILL_CATALOG:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            found_skills.add(skill)

    # Check dedicated Skills section
    skills_section_pattern = r'(?:SKILLS|TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES|TECHNOLOGIES)[\s:\-]+([\s\S]*?)(?=(?:EDUCATION|EXPERIENCE|PROJECTS|CERTIFICATIONS|ACHIEVEMENTS|\Z))'
    skills_sec = re.search(skills_section_pattern, text, re.IGNORECASE)
    if skills_sec:
        sec_text = skills_sec.group(1)
        # Split by comma, bullets, pipes, or newlines
        tokens = re.split(r'[,•|\n;]', sec_text)
        for token in tokens:
            cleaned = token.strip()
            if cleaned and 2 <= len(cleaned) <= 35 and not cleaned.startswith("http"):
                found_skills.add(cleaned)

    data["skills"] = sorted(list(found_skills))

    # 9. Extract Projects & Experience Sections
    proj_sec = re.search(r'(?:PROJECTS|ACADEMIC\s+PROJECTS|KEY\s+PROJECTS)[\s:\-]+([\s\S]*?)(?=(?:EXPERIENCE|SKILLS|EDUCATION|CERTIFICATIONS|\Z))', text, re.IGNORECASE)
    if proj_sec:
        proj_lines = [l.strip() for l in proj_sec.group(1).split('\n') if l.strip()]
        # Take key summary bullet lines
        data["projects"] = proj_lines[:5]

    exp_sec = re.search(r'(?:WORK\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT\s+HISTORY|INTERNSHIPS)[\s:\-]+([\s\S]*?)(?=(?:PROJECTS|SKILLS|EDUCATION|CERTIFICATIONS|\Z))', text, re.IGNORECASE)
    if exp_sec:
        exp_lines = [l.strip() for l in exp_sec.group(1).split('\n') if l.strip()]
        data["work_experience"] = exp_lines[:5]

    cert_sec = re.search(r'(?:CERTIFICATIONS|CERTIFICATES|LICENSES)[\s:\-]+([\s\S]*?)(?=(?:PROJECTS|SKILLS|EDUCATION|EXPERIENCE|\Z))', text, re.IGNORECASE)
    if cert_sec:
        cert_lines = [l.strip() for l in cert_sec.group(1).split('\n') if l.strip()]
        data["certifications"] = cert_lines[:5]

    return data


def parse_uploaded_file(file_path, original_filename):
    """
    Main entry point for parsing an uploaded file.
    Validates file, extracts text, and returns parsed data dict.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("Uploaded file was not found on server.")

    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError("File exceeds maximum allowed size of 10 MB.")

    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file format '{ext}'. Allowed formats: PDF, DOCX.")

    if ext == 'pdf':
        raw_text = extract_text_from_pdf(file_path)
    elif ext == 'docx':
        raw_text = extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported document format.")

    parsed_info = parse_document_text(raw_text)
    return parsed_info
