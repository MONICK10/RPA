# Module 6 · Screening agent (R3).
#
# The agentic layer: it looks at what modules 4 and 5 produced and CHOOSES the
# next action, instead of following one fixed path.
#
# Pure, exactly like m1-m5: plain data in, plain data out. No file reads, no
# file writes, no print, no clock, no network. Thresholds arrive as a dict
# (core/storage.py reads config/screening.json — rule 4).
#
# decide() returns one of four outcomes. "reroute" is NOT decided here: this
# module cannot see other job descriptions, so agent.py upgrades a "reject" to
# "reroute" when reroute() finds a better-fitting role.

from core.contract import CATEGORY_NAMES

DEFAULT_THRESHOLDS = {
    "shortlist_at": 60,
    "review_at": 40,
    "reroute_min_gain": 10,
    "score": "average",
}

SCORE_MODES = ("average", "readiness", "match")

SCORE_LABELS = {
    "average": "Average fit",
    "readiness": "Company readiness",
    "match": "Role fit",
}

# Decisions an alternative role must reach before it is worth rerouting to.
REROUTE_ELIGIBLE = ("shortlist", "review")

# Candidate-facing labels. CATEGORY_NAMES is the default; these two are
# overridden so the feedback note never shows a bare category code to a human
# ("SQL & Design" and "AI-Native Engineering" both contain their own code).
CANDIDATE_FACING_NAMES = {
    "SQL": "Databases and data modelling",
    "AI": "Machine learning",
    "OTHER": "Other technologies",
}

MAX_FEEDBACK_GAPS = 3
MAX_FEEDBACK_SKILLS = 6
MAX_FEEDBACK_STRENGTHS = 5


# ---------------------------------------------------------------------------
# thresholds
# ---------------------------------------------------------------------------

def resolve_thresholds(thresholds: dict | None) -> dict:
    """Merge a (possibly partial or malformed) config over the defaults.

    A missing key, a non-integer cutoff or an unknown score mode falls back to
    the default rather than raising — a bad config must never stop a screening
    run. review_at is clamped to shortlist_at so the review band can't invert.
    """
    merged = dict(DEFAULT_THRESHOLDS)
    for key in ("shortlist_at", "review_at", "reroute_min_gain"):
        value = (thresholds or {}).get(key, merged[key])
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        merged[key] = int(value)
    mode = (thresholds or {}).get("score", merged["score"])
    if isinstance(mode, str) and mode in SCORE_MODES:
        merged["score"] = mode
    merged["review_at"] = min(merged["review_at"], merged["shortlist_at"])
    return merged


def score_for(readiness: int | None, match: int | None, mode: str) -> int | None:
    """The single number the decision is made on. None when an input it needs
    is missing. Integer floor division keeps it deterministic — no rounding
    mode to argue about."""
    if mode == "readiness":
        return readiness if isinstance(readiness, int) else None
    if mode == "match":
        return match if isinstance(match, int) else None
    if not isinstance(readiness, int) or not isinstance(match, int):
        return None
    return (readiness + match) // 2


def _missing_inputs(readiness: int | None, match: int | None, mode: str) -> str:
    missing = []
    if mode in ("average", "readiness") and not isinstance(readiness, int):
        missing.append("company readiness")
    if mode in ("average", "match") and not isinstance(match, int):
        missing.append("role fit")
    return " and ".join(missing) if missing else "no usable score"


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------

def decide(readiness: int | None, match: int | None,
           thresholds: dict) -> tuple[str, str]:
    """Choose an outcome for one candidate against one role.

    Returns (decision, reason) where decision is one of
    "shortlist" | "review" | "reject" | "exception" and reason is one plain
    sentence a human can read in a spreadsheet cell.
    """
    t = resolve_thresholds(thresholds)
    mode = t["score"]
    score = score_for(readiness, match, mode)
    label = SCORE_LABELS[mode]

    if score is None:
        return ("exception", f"No score available ({_missing_inputs(readiness, match, mode)}) "
                             f"— this resume could not be scored.")

    if score >= t["shortlist_at"]:
        return ("shortlist", f"{label} {score} — at or above the shortlist line "
                             f"({t['shortlist_at']}); strong enough to move forward.")

    if score >= t["review_at"]:
        return ("review", f"{label} {score} — between review ({t['review_at']}) and "
                          f"shortlist ({t['shortlist_at']}); needs a human look.")

    return ("reject", f"{label} {score} — below the review line ({t['review_at']}).")


# ---------------------------------------------------------------------------
# reroute
# ---------------------------------------------------------------------------

def _role_key(role: str) -> str:
    return " ".join(str(role or "").split()).lower()


def _find_primary(candidate_results: list[dict], primary_role: str) -> dict | None:
    key = _role_key(primary_role)
    matches = [r for r in candidate_results if _role_key(r.get("role")) == key]
    if not matches:
        return None
    for row in matches:
        if row.get("primary"):
            return row
    return matches[0]


def reroute(candidate_results: list[dict], primary_role: str,
            min_gain: int) -> dict | None:
    """Pick a better-fitting open role for the same candidate.

    `candidate_results` is the same candidate scored against every open job
    description. Each row carries at least: role, company, score, decision
    (from `decide`), and optionally primary=True on the row for the role they
    actually applied to.

    Returns the best alternative only when it beats the primary role by at
    least `min_gain` AND itself reaches review or shortlist. Otherwise None.
    Ties break on role name then company, so the result is deterministic.
    """
    primary = _find_primary(candidate_results, primary_role)
    if primary is None or not isinstance(primary.get("score"), int):
        return None

    primary_key = _role_key(primary_role)
    alternatives = [
        row for row in candidate_results
        if _role_key(row.get("role")) != primary_key
        and row.get("decision") in REROUTE_ELIGIBLE
        and isinstance(row.get("score"), int)
    ]
    if not alternatives:
        return None

    best = sorted(
        alternatives,
        key=lambda r: (-r["score"], _role_key(r.get("role")), str(r.get("company") or "")),
    )[0]

    gain = best["score"] - primary["score"]
    if gain < min_gain:
        return None

    return {
        "role": best.get("role", ""),
        "company": best.get("company", ""),
        "score": best["score"],
        "decision": best["decision"],
        "gain": gain,
    }


# ---------------------------------------------------------------------------
# feedback
# ---------------------------------------------------------------------------

def _label(code: str, fallback: str = "") -> str:
    return (CANDIDATE_FACING_NAMES.get(code)
            or fallback
            or CATEGORY_NAMES.get(code)
            or "This area")


def _strength_lines(talent_check: dict) -> list[str]:
    rows = [r for r in (talent_check or {}).get("skillset_gap", []) if not r.get("gap")]
    rows = [r for r in rows if (r.get("required_level") or 0) > 0]
    rows.sort(key=lambda r: (-(r.get("required_level") or 0),
                             _label(r.get("category_code", ""), r.get("category_name", ""))))
    return [
        f"- **{_label(r.get('category_code', ''), r.get('category_name', ''))}** — "
        f"you're at the level this employer expects."
        for r in rows[:MAX_FEEDBACK_STRENGTHS]
    ]


def _gap_lines(talent_check: dict) -> list[str]:
    rows = [r for r in (talent_check or {}).get("skillset_gap", []) if r.get("gap")]
    rows.sort(key=lambda r: (-(r.get("gap_size") or 0), -(r.get("required_level") or 0),
                             _label(r.get("category_code", ""), r.get("category_name", ""))))
    lines = []
    for i, r in enumerate(rows[:MAX_FEEDBACK_GAPS], start=1):
        name = _label(r.get("category_code", ""), r.get("category_name", ""))
        required = r.get("required_level")
        have = r.get("candidate_level")
        lines.append(
            f"{i}. **{name}** — this employer looks for about {required} out of 10 here, "
            f"and your resume showed {have}."
        )
    return lines


def _missing_skill_lines(skill_match: dict) -> list[str]:
    names = []
    for s in (skill_match or {}).get("missing_skills", []):
        name = str(s.get("skill_name") or "").strip()
        if name and name not in names:
            names.append(name)
    return [f"- {n}" for n in names[:MAX_FEEDBACK_SKILLS]]


def _closing(summary: dict) -> str:
    decision = (summary or {}).get("decision", "")
    if decision == "shortlist":
        return ("You're being put forward for this role. Expect to hear about next "
                "steps shortly.")
    if decision == "review":
        return ("You're close enough that a person is reading your application "
                "rather than a filter. The points above are what they'll ask about.")
    if decision == "reroute":
        role = (summary or {}).get("rerouted_to_role") or "another open role"
        company = (summary or {}).get("rerouted_to_company") or ""
        where = f"{role} at {company}" if company else role
        return (f"This particular role isn't your closest match, but **{where}** lines up "
                f"better with what your resume already shows — we've passed you to that one.")
    if decision == "reject":
        return ("This role isn't the right fit right now. The three points above are the "
                "shortest route to changing that — none of them need a new degree, just "
                "evidence on the page.")
    return "Here's where your application stands today."


def feedback_markdown(summary: dict, talent_check: dict, skill_match: dict) -> str:
    """Short, kind, specific feedback for one candidate.

    Strengths first, then the top three gaps in plain names, then the skills
    this posting named that the resume didn't show. Reuses the Feature Addendum
    F5 tone rules: plain language, strengths before gaps, no category codes and
    no JSON field names anywhere in the output.
    """
    summary = summary or {}
    name = str(summary.get("candidate_name") or "").strip() or "there"
    role = str(summary.get("role") or "").strip()
    company = str(summary.get("company") or "").strip()

    heading = " · ".join(p for p in ("Where you stand", role, company) if p)
    out = [f"# {heading}", ""]
    out.append(f"Hi {name} — here's what we read from your resume, and how it lines up "
               f"with what this employer looks for.")
    out.append("")

    out.append("## What's already working")
    out.append("")
    strengths = _strength_lines(talent_check)
    if strengths:
        out.extend(strengths)
    else:
        out.append("- We couldn't credit a clear strength from the resume text yet. "
                   "That's usually a writing problem, not a skills problem — the points "
                   "below are the fastest way to change it.")
    out.append("")

    out.append("## The areas holding you back most")
    out.append("")
    gaps = _gap_lines(talent_check)
    if gaps:
        out.extend(gaps)
    else:
        out.append("1. Nothing stood out — you meet the level this employer looks for "
                   "across the board.")
    out.append("")

    out.append("## Named in this job description, not visible in your resume")
    out.append("")
    missing = _missing_skill_lines(skill_match)
    if missing:
        out.extend(missing)
        out.append("")
        out.append("If you have used any of these, name them explicitly — we can only "
                   "credit what the page actually says.")
    else:
        out.append("- Nothing. Every skill this posting names showed up in your resume.")
    out.append("")

    out.append("## What happens next")
    out.append("")
    out.append(_closing(summary))
    out.append("")

    return "\n".join(out)
