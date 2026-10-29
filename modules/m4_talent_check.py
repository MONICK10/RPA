# Talent Check — candidate vs a COMPANY'S hiring bar across the 12 fixed skillsets.
# Never reads a JD. Pure function: no file I/O.

from core.coding_profiles import merge_verified_levels, verified_levels_from_coding_profiles
from core.contract import CATEGORY_CODES, CATEGORY_NAMES
from core.planning import effort_hours
from core.skill_dictionary import SKILL_KEYWORDS, keyword_in_text

VERDICT_THRESHOLDS = (
    (85, "Ready"),
    (70, "Nearly ready"),
    (50, "Developing"),
)


def _estimate_from_resume_and_profile(profile: dict) -> dict[str, int]:
    skills = profile.get("skills", [])
    narrative_text = " ".join(
        profile.get("hackathons", []) + profile.get("internships", [])
    ).lower()
    cert_text = " ".join(profile.get("certifications", [])).lower()

    levels: dict[str, int] = {}
    for code in CATEGORY_CODES:
        skills_in_cat = [s for s in skills if s.get("category_code") == code]
        level = 0

        if skills_in_cat:
            level += 4

        if any(s.get("confidence") == "high" for s in skills_in_cat):
            level += 2
        elif any(s.get("confidence") == "medium" for s in skills_in_cat):
            level += 1

        if len(skills_in_cat) >= 3:
            level += 1

        keywords = SKILL_KEYWORDS.get(code, [])
        if any(keyword_in_text(narrative_text, kw) for kw in keywords):
            level += 2

        if any(keyword_in_text(cert_text, kw) for kw in keywords):
            level += 1

        levels[code] = min(level, 10)

    return levels


def estimate_candidate_levels_detailed(profile: dict) -> dict[str, dict]:
    """Per-category detail: level (final, merged), estimated_level, verified_level,
    source ("estimated"|"verified"), evidence. F1.6 merge rule: verified coding-profile
    data (DSA/COD/APTI only) raises a level, it never lowers one."""
    estimated = _estimate_from_resume_and_profile(profile)
    verified = verified_levels_from_coding_profiles(profile.get("coding_profiles"))
    return merge_verified_levels(estimated, verified)


def estimate_candidate_levels(profile: dict) -> dict[str, int]:
    return {code: detail["level"] for code, detail in estimate_candidate_levels_detailed(profile).items()}


def _verdict(score: int) -> str:
    for threshold, label in VERDICT_THRESHOLDS:
        if score >= threshold:
            return label
    return "Significant gaps"


def run_talent_check(profile: dict, company: str, company_data: dict) -> dict:
    candidate_detail = estimate_candidate_levels_detailed(profile)
    company_entry = company_data.get(company, {})
    skillsets = company_entry.get("skillsets", {})

    skillset_gap = []
    achieved = 0
    total = 0

    for code in CATEGORY_CODES:
        required_entry = skillsets.get(code)
        if required_entry is None:
            continue

        required_level = required_entry["required_level"]
        detail = candidate_detail[code]
        candidate_level = detail["level"]
        gap_size = max(0, required_level - candidate_level)

        achieved += min(candidate_level, required_level)
        total += required_level

        skillset_gap.append({
            "category_code": code,
            "category_name": CATEGORY_NAMES[code],
            "required_level": required_level,
            "required_band": required_entry.get("band", "NA"),
            "candidate_level": candidate_level,
            "estimated_level": detail["estimated_level"],
            "verified_level": detail["verified_level"],
            "level_source": detail["source"],
            "gap": candidate_level < required_level,
            "gap_size": gap_size,
            "effort_hours": effort_hours(code, gap_size),
        })

    readiness_score = round(100 * achieved / total) if total > 0 else 0

    top_gaps = [
        g["category_code"]
        for g in sorted(
            skillset_gap,
            key=lambda g: (-g["gap_size"], -g["required_level"]),
        )[:3]
    ]

    return {
        "company": company,
        "readiness_score": readiness_score,
        "verdict": _verdict(readiness_score),
        "skillset_gap": skillset_gap,
        "top_gaps": top_gaps,
    }
