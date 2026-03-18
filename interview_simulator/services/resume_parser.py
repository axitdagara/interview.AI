import re

from PyPDF2 import PdfReader


SKILL_LIBRARY = [
    "python",
    "flask",
    "django",
    "fastapi",
    "sql",
    "sqlite",
    "mysql",
    "postgresql",
    "machine learning",
    "deep learning",
    "nlp",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "html",
    "css",
    "javascript",
    "bootstrap",
    "react",
    "git",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "communication",
    "problem solving",
    "teamwork",
]

ROLE_SKILLS = {
    "Software Engineer": {
        "python",
        "sql",
        "flask",
        "git",
        "problem solving",
        "communication",
    },
    "Data Scientist": {
        "python",
        "machine learning",
        "pandas",
        "numpy",
        "scikit-learn",
        "sql",
    },
    "Frontend Developer": {
        "html",
        "css",
        "javascript",
        "bootstrap",
        "react",
        "communication",
    },
    "AI Engineer": {
        "python",
        "machine learning",
        "deep learning",
        "nlp",
        "tensorflow",
        "pytorch",
    },
}


def extract_text_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages)


def extract_skills(text):
    low_text = (text or "").lower()
    found = []

    for skill in SKILL_LIBRARY:
        pattern = rf"\b{re.escape(skill.lower())}\b"
        if re.search(pattern, low_text):
            found.append(skill)

    return sorted(set(found))


def compute_role_match(skills, role):
    required = ROLE_SKILLS.get(role, set())
    if not required:
        return 0.0, [], []

    skill_set = {skill.lower() for skill in skills}
    matched = sorted(skill for skill in required if skill in skill_set)
    missing = sorted(skill for skill in required if skill not in skill_set)
    score = round((len(matched) / len(required)) * 100, 2)

    return score, matched, missing
