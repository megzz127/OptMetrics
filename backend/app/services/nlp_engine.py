"""
NLP and Semantic Matching Engine for OptMetrics.
Implements hybrid matching:
1. Exact & normalized field matching.
2. Domain-specific synonym, alias, and keyword matching.
3. Vector similarity via sentence-transformers (when available) or TF-IDF character n-gram cosine similarity.
4. Token overlap / Levenshtein ratio.
"""

import re
import difflib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Try loading sentence-transformers if present; otherwise fallback smoothly
SENTENCE_TRANSFORMER_MODEL = None
_SENTENCE_TRANSFORMER_TRIED = False


def get_sentence_transformer():
    """Lazily load sentence-transformers model if installed in the environment."""
    global SENTENCE_TRANSFORMER_MODEL, _SENTENCE_TRANSFORMER_TRIED
    if _SENTENCE_TRANSFORMER_TRIED:
        return SENTENCE_TRANSFORMER_MODEL
    _SENTENCE_TRANSFORMER_TRIED = True
    try:
        from sentence_transformers import SentenceTransformer
        # Use lightweight MiniLM model
        SENTENCE_TRANSFORMER_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        # Fallback to TF-IDF & heuristic similarity
        SENTENCE_TRANSFORMER_MODEL = None
    return SENTENCE_TRANSFORMER_MODEL


# Alias and synonym dictionary mapping standard profile keys to common form labels
PROFILE_FIELD_ALIASES = {
    "full_name": [
        "full name", "applicant name", "candidate name", "name", "your name",
        "student name", "legal name", "first and last name", "complete name",
        "participant name", "attendee name"
    ],
    "email": [
        "email", "email address", "e-mail", "mail id", "email id", "contact email",
        "primary email", "applicant email", "official email", "personal email"
    ],
    "phone": [
        "phone", "phone number", "mobile number", "contact number", "telephone",
        "cell phone", "mobile", "whatsapp number", "primary phone", "contact no", "ph no"
    ],
    "address": [
        "address", "current address", "residential address", "home address",
        "postal address", "mailing address", "street address", "location",
        "permanent address", "city state"
    ],
    "date_of_birth": [
        "date of birth", "dob", "birth date", "birthday", "birthdate", "d.o.b."
    ],
    "college": [
        "college", "university", "institution name", "institution", "school name",
        "college name", "university/college", "alma mater", "current institute",
        "educational institution", "campus name", "college or university"
    ],
    "degree": [
        "degree", "current degree", "pursuing degree", "qualification",
        "undergraduate degree", "postgraduate degree", "highest qualification",
        "degree/diploma", "program", "course enrolled", "current program"
    ],
    "branch": [
        "branch", "major", "field of study", "department", "stream",
        "specialization", "course", "engineering branch", "discipline",
        "branch of study", "major/concentration"
    ],
    "graduation_year": [
        "graduation year", "expected graduation year", "year of graduation",
        "pass out year", "batch", "passing year", "completion year",
        "grad year", "year of passing", "expected year of completion"
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "technologies known",
        "key skills", "programming languages", "tools & technologies",
        "competencies", "areas of expertise", "it skills", "skill set"
    ],
    "projects": [
        "projects", "relevant project experience", "academic projects",
        "key projects", "notable projects", "project details", "personal projects",
        "portfolio projects", "project description", "major projects"
    ],
    "work_experience": [
        "work experience", "experience", "employment history", "prior experience",
        "internships", "professional experience", "past roles", "job experience",
        "previous employment", "internship experience"
    ],
    "certifications": [
        "certifications", "licenses", "certificates", "credentials",
        "courses completed", "accreditations", "professional certifications"
    ]
}

# Standard stop phrases in form questions
STOP_PHRASES = [
    r'\bplease\s+enter\s+your\b',
    r'\bwhat\s+is\s+your\b',
    r'\bwhat\s+is\b',
    r'\benter\s+your\b',
    r'\bprovide\s+your\b',
    r'\bplease\s+specify\b',
    r'\bwrite\s+down\b',
    r'\bspecify\b',
    r'\bmention\b',
    r'\btype\s+here\b',
    r'\byour\b',
    r'[*:\?]'
]


def clean_form_label(label):
    """Normalize and clean a field label or question text."""
    if not label:
        return ""
    text = label.strip().lower()
    for phrase in STOP_PHRASES:
        text = re.sub(phrase, ' ', text, flags=re.IGNORECASE)
    # Remove extra symbols and multiple whitespace
    text = re.sub(r'[^a-z0-9\s/_\-]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def compute_string_similarity(str1, str2):
    """Compute string similarity using SequenceMatcher (Levenshtein-like ratio)."""
    if not str1 or not str2:
        return 0.0
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def compute_tfidf_similarity(text1, text2):
    """
    Compute sub-word character n-gram cosine similarity using TF-IDF.
    High accuracy for capturing typos, plurals, prefixes, and word order differences.
    """
    if not text1 or not text2:
        return 0.0
    if text1.strip().lower() == text2.strip().lower():
        return 1.0
    try:
        vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
        tfidf = vectorizer.fit_transform([text1, text2])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return float(sim)
    except Exception:
        return compute_string_similarity(text1, text2)


def compute_semantic_embedding_similarity(text1, text2):
    """
    Compute cosine similarity between two sentences using sentence-transformers
    if installed; otherwise returns None.
    """
    model = get_sentence_transformer()
    if model is None:
        return None
    try:
        embeddings = model.encode([text1, text2])
        sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return float(sim)
    except Exception:
        return None
