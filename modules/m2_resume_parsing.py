# Resume Parsing — resume text -> extracted skill list + structured sections.
# Resumes are messy: every step degrades gracefully rather than raising.

import re

from core.contract import validate_skill_list
from core.skill_dictionary import extract_skills

SECTION_KEYWORDS = {
    "education": ["education", "academic"],
    "projects": ["project"],
    "experience": ["experience", "internship", "work history", "employment", "achievement"],
    "certifications": ["certification", "certificate", "license"],
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _is_heading(line: str) -> bool:
    if not line or line.endswith("."):
        return False
    if len(line) > 40:
        return False
    words = line.split()
    if not words or len(words) > 5:
        return False
    return line.isupper() or line.istitle()


def _classify_heading(line: str) -> str | None:
    lower = line.lower()
    for key, keywords in SECTION_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return key
    return None


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {k: [] for k in SECTION_KEYWORDS}
    current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_heading(line):
            current = _classify_heading(line)
            continue
        if current:
            cleaned = line.lstrip("•-*▪●○ \t")
            if cleaned:
                sections[current].append(cleaned)

    return sections


_NAME_LINE_BLOCKLIST = ("page ", "resume", "curriculum vitae", "hackathon", "test data")


def _looks_like_name(line: str) -> bool:
    words = line.split()
    if not (1 <= len(words) <= 4):
        return False
    if any(ch.isdigit() for ch in line):
        return False
    lower = line.lower()
    return not any(kw in lower for kw in _NAME_LINE_BLOCKLIST)


def _first_nonempty_line(text: str) -> str:
    lines = [raw_line.strip() for raw_line in text.splitlines() if raw_line.strip()]
    for line in lines:
        if _looks_like_name(line):
            return line
    return lines[0] if lines else ""


def _extract_email(text: str) -> str:
    match = EMAIL_RE.search(text)
    return match.group(0) if match else ""


def parse_resume(text: str, source_file: str, use_llm: bool = False) -> dict:
    skills = None
    if use_llm:
        try:
            from core.llm_extract import extract_skills as llm_extract_skills
            skills = llm_extract_skills(text, source_hint=source_file)
        except Exception:
            skills = None
    if skills is None:
        skills = extract_skills(text, source_hint=source_file)

    raw_sections = _split_sections(text)

    structured = {
        "education": " ".join(raw_sections["education"]),
        "projects": raw_sections["projects"],
        "experience": raw_sections["experience"],
        "certifications": raw_sections["certifications"],
    }

    payload = {
        "source_type": "resume",
        "source_file": source_file,
        "company": "",
        "role": "",
        "skills": skills,
        "candidate_name": _first_nonempty_line(text),
        "email": _extract_email(text),
        "structured": structured,
    }
    validate_skill_list(payload)
    return payload
