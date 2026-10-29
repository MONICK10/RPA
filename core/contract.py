# RADIX Talent Match — single source of truth for the data contract.
# Every module imports from here. A second copy of the category list anywhere is a bug.

CATEGORY_CODES = [
    "DSA", "COD", "OOD", "APTI", "COMM", "AI",
    "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS",
]
OTHER = "OTHER"
ALL_CODES = CATEGORY_CODES + [OTHER]

CATEGORY_NAMES = {
    "DSA":   "Data Structures & Algorithms",
    "COD":   "Coding",
    "OOD":   "Object Oriented Programming & Design",
    "APTI":  "Aptitude & Problem Solving",
    "COMM":  "Communication Skills",
    "AI":    "AI-Native Engineering",
    "CLOUD": "DevOps & Cloud",
    "SQL":   "SQL & Design",
    "SWE":   "Software Engineering",
    "SYSD":  "System Design & Architecture",
    "NETW":  "Computer Networking",
    "OS":    "Operating Systems",
    "OTHER": "Other",
}

CONFIDENCE_LEVELS = ("verified", "high", "medium", "low")
CONFIDENCE_WEIGHT = {"verified": 4, "high": 3, "medium": 2, "low": 1}

ALIASES = {
    "js": "javascript", "nodejs": "node", "reactjs": "react",
    "postgres": "postgresql", "ms sql": "sqlserver", "k8s": "kubernetes",
    "ml": "machinelearning", "dl": "deeplearning", "nlp": "naturallanguageprocessing",
    "ci cd": "cicd", "gcp": "googlecloud", "aws": "amazonwebservices",
    "powerbi": "powerbi", "oop": "objectorientedprogramming",
}

def normalise_skill_name(name: str) -> str:
    """Lowercase, strip, remove separator punctuation, apply alias table."""
    if name is None:
        return ""
    text = name.lower().strip()
    for alias, target in ALIASES.items():
        if text == alias:
            text = target
            break
    for ch in (".", "-", "_", "/", " "):
        text = text.replace(ch, "")
    return text


def validate_skill(skill: dict) -> None:
    if not isinstance(skill, dict):
        raise ValueError(f"skill must be a dict, got {type(skill).__name__}")

    skill_name = skill.get("skill_name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        raise ValueError(f"skill.skill_name must be a non-empty string, got {skill_name!r}")

    category_code = skill.get("category_code")
    if category_code not in ALL_CODES:
        raise ValueError(
            f"skill.category_code {category_code!r} is not one of ALL_CODES: {ALL_CODES}"
        )

    evidence = skill.get("evidence")
    if not isinstance(evidence, str):
        raise ValueError(f"skill.evidence must be a string, got {type(evidence).__name__}")

    confidence = skill.get("confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(
            f"skill.confidence {confidence!r} must be one of {CONFIDENCE_LEVELS}"
        )


def validate_skill_list(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"skill list payload must be a dict, got {type(payload).__name__}")

    source_type = payload.get("source_type")
    if source_type not in ("jd", "resume"):
        raise ValueError(f"source_type must be 'jd' or 'resume', got {source_type!r}")

    for key in ("source_file", "company", "role"):
        if not isinstance(payload.get(key), str):
            raise ValueError(f"payload.{key} must be a string, got {payload.get(key)!r}")

    skills = payload.get("skills")
    if not isinstance(skills, list):
        raise ValueError(f"payload.skills must be a list, got {type(skills).__name__}")
    for skill in skills:
        validate_skill(skill)

    if source_type == "resume":
        if not isinstance(payload.get("candidate_name"), str):
            raise ValueError("resume payload must have a string candidate_name")
        structured = payload.get("structured")
        if not isinstance(structured, dict):
            raise ValueError("resume payload must have a structured dict")
        for key in ("education", "projects", "experience", "certifications"):
            if key not in structured:
                raise ValueError(f"structured is missing key {key!r}")


def validate_profile(profile: dict) -> None:
    if not isinstance(profile, dict):
        raise ValueError(f"profile must be a dict, got {type(profile).__name__}")

    for key in ("name", "email", "education"):
        if not isinstance(profile.get(key), str):
            raise ValueError(f"profile.{key} must be a string, got {profile.get(key)!r}")

    skills = profile.get("skills")
    if not isinstance(skills, list):
        raise ValueError(f"profile.skills must be a list, got {type(skills).__name__}")
    for skill in skills:
        validate_skill(skill)

    for key in ("hackathons", "internships", "certifications", "preferred_roles"):
        value = profile.get(key)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"profile.{key} must be a list of strings, got {value!r}")

    if not isinstance(profile.get("cv_file"), str):
        raise ValueError(f"profile.cv_file must be a string, got {profile.get('cv_file')!r}")

    if "coding_profiles" in profile:
        validate_coding_profiles(profile["coding_profiles"])


CODING_PLATFORMS = ("leetcode", "hackerrank")
CODING_PROFILE_SOURCES = ("fetched", "cached", "manual")


def validate_coding_profiles(block: dict) -> None:
    """New, optional profile.json block (F1). Backward compatible: absent entirely,
    or either platform set to None, are both valid — this is opt-in evidence."""
    if not isinstance(block, dict):
        raise ValueError(f"profile.coding_profiles must be a dict, got {type(block).__name__}")

    for platform in CODING_PLATFORMS:
        entry = block.get(platform)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            raise ValueError(f"coding_profiles.{platform} must be a dict or null, got {type(entry).__name__}")
        if not isinstance(entry.get("username"), str) or not entry["username"].strip():
            raise ValueError(f"coding_profiles.{platform}.username must be a non-empty string")
        source = entry.get("source")
        if source not in CODING_PROFILE_SOURCES:
            raise ValueError(f"coding_profiles.{platform}.source must be one of {CODING_PROFILE_SOURCES}, got {source!r}")
