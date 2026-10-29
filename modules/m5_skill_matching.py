# Skill Matching — candidate vs ONE JD's extracted skill list. Never reads the company dataset.

import difflib

from core.contract import normalise_skill_name

WEIGHT = {"high": 3, "medium": 2, "low": 1}
_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}
FUZZY_CUTOFF = 0.85


def match_skills(profile: dict, jd_payload: dict) -> dict:
    jd_skills = jd_payload.get("skills", [])

    result = {
        "jd_source_file": jd_payload.get("source_file", ""),
        "company": jd_payload.get("company", ""),
        "role": jd_payload.get("role", ""),
        "match_score": 0,
        "matched_skills": [],
        "missing_skills": [],
        "category_coverage": {},
    }

    if not jd_skills:
        result["message"] = "JD has no extracted skills to match against."
        return result

    profile_by_norm = {
        normalise_skill_name(s["skill_name"]): s for s in profile.get("skills", [])
    }
    profile_norm_names = list(profile_by_norm.keys())

    matched_skills = []
    missing_skills = []
    category_totals: dict[str, list[int]] = {}  # code -> [matched_count, total_count]
    earned = 0

    for jd_skill in jd_skills:
        code = jd_skill["category_code"]
        category_totals.setdefault(code, [0, 0])
        category_totals[code][1] += 1

        jd_norm = normalise_skill_name(jd_skill["skill_name"])
        is_matched = False

        if jd_norm in profile_by_norm:
            matched_skills.append({
                "jd_skill": jd_skill["skill_name"],
                "profile_skill": profile_by_norm[jd_norm]["skill_name"],
                "how": "exact",
            })
            is_matched = True
        else:
            close = difflib.get_close_matches(
                jd_norm, profile_norm_names, n=1, cutoff=FUZZY_CUTOFF
            )
            if close:
                best = close[0]
                similarity = difflib.SequenceMatcher(None, jd_norm, best).ratio()
                matched_skills.append({
                    "jd_skill": jd_skill["skill_name"],
                    "profile_skill": profile_by_norm[best]["skill_name"],
                    "how": "fuzzy",
                    "similarity": round(similarity, 2),
                })
                is_matched = True

        if is_matched:
            category_totals[code][0] += 1
            earned += WEIGHT[jd_skill["confidence"]]
        else:
            missing_skills.append({
                "skill_name": jd_skill["skill_name"],
                "category_code": code,
                "confidence": jd_skill["confidence"],
            })

    possible = sum(WEIGHT[s["confidence"]] for s in jd_skills)
    match_score = round(100 * earned / possible) if possible else 0

    missing_skills.sort(key=lambda s: -_CONFIDENCE_RANK[s["confidence"]])

    category_coverage = {
        code: round(matched / total, 2) if total else 0.0
        for code, (matched, total) in category_totals.items()
    }

    result["match_score"] = match_score
    result["matched_skills"] = matched_skills
    result["missing_skills"] = missing_skills
    result["category_coverage"] = category_coverage
    return result
