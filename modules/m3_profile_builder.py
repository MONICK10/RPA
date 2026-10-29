# Profile Builder — resume prefill + manual form input -> candidate profile.

from core.contract import normalise_skill_name, validate_profile

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

_EMPTY_PREFILL = {
    "name": "", "email": "", "education": "", "skills": [],
    "hackathons": [], "internships": [], "certifications": [],
    "preferred_roles": [], "cv_file": "",
}

_EMPTY_CODING_PROFILES = {"leetcode": None, "hackerrank": None}


def prefill_from_resume(resume_payload: dict) -> dict:
    structured = resume_payload.get("structured", {})
    source_file = resume_payload.get("source_file", "")
    return {
        "name": resume_payload.get("candidate_name", ""),
        "email": resume_payload.get("email", ""),
        "education": structured.get("education", ""),
        "skills": resume_payload.get("skills", []),
        "hackathons": [],
        "internships": structured.get("experience", []),
        "certifications": structured.get("certifications", []),
        "preferred_roles": [],
        "cv_file": f"data/resumes/{source_file}" if source_file else "",
    }


def _merge_skills(resume_skills: list[dict], manual_skills: list[dict]) -> list[dict]:
    by_norm: dict[str, dict] = {}
    for skill in resume_skills + manual_skills:
        key = normalise_skill_name(skill["skill_name"])
        existing = by_norm.get(key)
        if existing is None or _CONFIDENCE_RANK[skill["confidence"]] > _CONFIDENCE_RANK[existing["confidence"]]:
            by_norm[key] = skill
    return sorted(by_norm.values(), key=lambda s: (s["category_code"], s["skill_name"]))


def _normalise_manual_skills(manual_skills_raw: list) -> list[dict]:
    manual_skills = []
    for item in manual_skills_raw:
        if isinstance(item, str):
            name, code = item, "OTHER"
        else:
            name = item.get("skill_name", "")
            code = item.get("category_code", "OTHER")
        if not name:
            continue
        manual_skills.append({
            "skill_name": name,
            "category_code": code,
            "evidence": "self-reported",
            "confidence": "high",
        })
    return manual_skills


def build_profile(form_data: dict, resume_payload: dict | None = None) -> dict:
    prefill = prefill_from_resume(resume_payload) if resume_payload else dict(_EMPTY_PREFILL)

    def pick(key: str, is_list: bool = False):
        value = form_data.get(key)
        if value not in (None, "", []):
            return value
        return prefill.get(key, [] if is_list else "")

    manual_skills = _normalise_manual_skills(form_data.get("manual_skills", []))
    merged_skills = _merge_skills(prefill.get("skills", []), manual_skills)

    profile = {
        "name": pick("name"),
        "email": pick("email"),
        "education": pick("education"),
        "skills": merged_skills,
        "hackathons": pick("hackathons", is_list=True),
        "internships": pick("internships", is_list=True),
        "certifications": pick("certifications", is_list=True),
        "preferred_roles": pick("preferred_roles", is_list=True),
        "cv_file": pick("cv_file"),
        "coding_profiles": form_data.get("coding_profiles") or dict(_EMPTY_CODING_PROFILES),
    }
    validate_profile(profile)
    return profile
