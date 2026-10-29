# F2 (what-if simulator) + F3 (effort-ranked gaps). Pure functions — no file I/O,
# both operate on an already-computed talent_check_result.json payload.

WEEKLY_HOURS_DEFAULT = 16

# F3 — hours per level point, by category. Estimates, used to rank, not to promise.
HOURS_PER_LEVEL = {
    "SQL":   12,   # fastest — bounded syntax, immediate feedback
    "CLOUD": 15,
    "APTI":  15,
    "NETW":  18,
    "OS":    18,
    "COD":   20,
    "OOD":   20,
    "SWE":   20,
    "COMM":  20,
    "DSA":   30,   # slow — needs sustained practice volume
    "SYSD":  30,
    "AI":    35,   # slowest — deep prerequisites
}


def effort_hours(category_code: str, gap_size: int) -> int:
    return gap_size * HOURS_PER_LEVEL.get(category_code, 20)


# ---------------------------------------------------------------------------
# F3 — three ranked views of the same gap list
# ---------------------------------------------------------------------------

def compute_gap_views(skillset_gap: list[dict]) -> dict:
    """Returns {"recommended", "biggest_impact", "quickest_wins", "already_met"}.
    Each row: category_code, category_name, gap_size, required_level,
    candidate_level, impact_points, effort_hours, roi, stars (1-4, relative)."""
    total_required = sum(g["required_level"] for g in skillset_gap) or 1

    rows = []
    already_met = []
    for g in skillset_gap:
        if not g.get("gap"):
            already_met.append(g["category_code"])
            continue
        code = g["category_code"]
        gap_size = g["gap_size"]
        hours = effort_hours(code, gap_size)
        impact = round(gap_size / total_required * 100, 1)
        roi = round(impact / hours * 100, 2) if hours else 0.0
        rows.append({
            "category_code": code,
            "category_name": g.get("category_name", code),
            "gap_size": gap_size,
            "required_level": g["required_level"],
            "candidate_level": g["candidate_level"],
            "impact_points": impact,
            "effort_hours": hours,
            "roi": roi,
        })

    max_roi = max((r["roi"] for r in rows), default=0) or 1
    for r in rows:
        r["stars"] = max(1, round(r["roi"] / max_roi * 4)) if rows else 0

    return {
        "recommended": sorted(rows, key=lambda r: -r["roi"]),
        "biggest_impact": sorted(rows, key=lambda r: -r["impact_points"]),
        "quickest_wins": sorted(rows, key=lambda r: r["effort_hours"]),
        "already_met": already_met,
    }


# ---------------------------------------------------------------------------
# F2 — "what if" simulator
# ---------------------------------------------------------------------------

def simulate(talent_check: dict, overrides: dict[str, int],
             weekly_hours: int = WEEKLY_HOURS_DEFAULT) -> dict:
    """overrides: {category_code: target_level}, one entry per dragged slider.
    A slider can only move between the candidate's current level and the
    required level (credit is capped anyway — see F2 requirements). Never
    writes anywhere; it's a projection over the already-computed skillset_gap."""
    skillset_gap = talent_check.get("skillset_gap", [])
    baseline_readiness = talent_check.get("readiness_score", 0)

    achieved = 0
    total = 0
    total_hours = 0

    for g in skillset_gap:
        code = g["category_code"]
        required = g["required_level"]
        candidate = g["candidate_level"]
        target = candidate
        if code in overrides:
            target = max(candidate, min(overrides[code], required))
            total_hours += effort_hours(code, target - candidate)
        achieved += min(target, required)
        total += required

    new_readiness = round(100 * achieved / total) if total else 0
    weeks = round(total_hours / weekly_hours, 1) if weekly_hours else 0.0

    return {
        "baseline_readiness": baseline_readiness,
        "new_readiness": new_readiness,
        "delta": new_readiness - baseline_readiness,
        "effort_hours": total_hours,
        "weeks": weeks,
        "weekly_hours": weekly_hours,
    }
