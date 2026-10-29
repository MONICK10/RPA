# F4 — best-fit company finder. Loops Talent Check over every company; ~98
# companies x 12 integer comparisons is milliseconds, no caching needed.

from modules.m4_talent_check import run_talent_check


def rank_companies(profile: dict, company_data: dict, top_n: int | None = None) -> list[dict]:
    """Run Talent Check against every company. Returns rows sorted by readiness
    descending: company, readiness_score, verdict, top_gap (single category name)."""
    rows = []
    for company in company_data:
        result = run_talent_check(profile, company, company_data)
        top_gaps = result.get("top_gaps") or []
        top_gap_name = None
        if top_gaps:
            gap_lookup = {g["category_code"]: g for g in result["skillset_gap"]}
            top_gap_name = gap_lookup[top_gaps[0]]["category_name"]

        rows.append({
            "company": company,
            "readiness_score": result["readiness_score"],
            "verdict": result["verdict"],
            "top_gap": top_gap_name,
        })

    rows.sort(key=lambda r: -r["readiness_score"])
    return rows[:top_n] if top_n else rows
