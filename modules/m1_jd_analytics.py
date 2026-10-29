# JD Analytics — JD text -> extracted skill list. Never reads the company dataset.

from core.contract import validate_skill_list
from core.skill_dictionary import extract_skills

FOCUS_HEADINGS = [
    "key responsibilities",
    "what we're looking for",
    "what we are looking for",
    "requirements",
    "qualifications",
    "preferred qualifications",
]

BOUNDARY_HEADINGS = FOCUS_HEADINGS + [
    "benefits",
    "about us",
    "about the company",
    "how to apply",
    "equal opportunity",
    "compensation",
    "perks",
]


def _focus_sections(text: str) -> str:
    lower = text.lower()
    positions = []
    for heading in FOCUS_HEADINGS:
        idx = lower.find(heading)
        if idx != -1:
            positions.append((idx, heading))
    positions.sort()

    sections = []
    for idx, heading in positions:
        start = idx + len(heading)
        end = len(text)
        for boundary in BOUNDARY_HEADINGS:
            bidx = lower.find(boundary, start)
            if bidx != -1 and bidx < end:
                end = bidx
        sections.append(text[start:end])

    return " ".join(sections)


def analyse_jd(text: str, source_file: str, company: str = "", role: str = "",
                use_llm: bool = False) -> dict:
    focus_text = _focus_sections(text)
    # weight focused sections by concatenating them a second time onto the search text
    search_text = text + " " + focus_text

    skills = None
    if use_llm:
        try:
            from core.llm_extract import extract_skills as llm_extract_skills
            skills = llm_extract_skills(search_text, source_hint=source_file)
        except Exception:
            skills = None
    if skills is None:
        skills = extract_skills(search_text, source_hint=source_file)

    payload = {
        "source_type": "jd",
        "source_file": source_file,
        "company": company,
        "role": role,
        "skills": skills,
    }
    validate_skill_list(payload)
    return payload
