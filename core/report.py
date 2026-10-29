# F5 — the final report. Pure function: no file I/O (storage.py writes it,
# st.download_button serves it). Markdown only — HTML/PDF was explicitly
# de-scoped ("do not block on PDF").

import datetime

from core.contract import CATEGORY_NAMES
from core.planning import WEEKLY_HOURS_DEFAULT, compute_gap_views, simulate

CALC_EXPLANATION = """\
**Company readiness** compares your level (1-10) in each of the 12 fixed skillsets \
against that company's required level for the same skillset. Credit for any one \
skillset is capped at the required level — being far above the bar in one area \
never compensates for falling short in another. The score is the percentage of \
total required points you've reached across all 12.

**Role fit** is different: it compares your profile only against the skills this \
specific job posting names, weighted by how strongly the posting emphasises each \
one. It never reads the company's general bar, and readiness never reads this \
posting — that separation is why the two scores can diverge.

**Verified data** (a LeetCode or HackerRank profile) can raise your estimated level \
in Data Structures & Algorithms, Coding, or Aptitude — never lower it. A candidate \
with strong projects but a thin coding-practice profile isn't punished for not \
grinding problems.

**Effort-hour estimates** come from a fixed hours-per-level table, calibrated by \
how bounded and practicable each skill is (SQL is fast to move; AI is slow). They \
exist to *rank* gaps against each other, not to promise a delivery date.

This estimator is a heuristic built for this hackathon's fixed rubric. It has not \
been validated against real hiring outcomes, and should be read as a structured \
starting point, not a verdict.
"""


def _fmt_pct(n) -> str:
    return f"{n:g}"


def _strengths(talent_check: dict) -> list[dict]:
    return [g for g in talent_check["skillset_gap"] if not g.get("gap")]


def _evidence_counts(profile: dict) -> dict:
    skills = profile.get("skills", [])
    resume_skills = [s for s in skills if s.get("evidence") not in (None, "self-reported")]
    manual_skills = [s for s in skills if s.get("evidence") == "self-reported"]
    coding = profile.get("coding_profiles") or {}
    return {
        "resume_count": len(resume_skills),
        "manual_count": len(manual_skills),
        "leetcode": coding.get("leetcode"),
        "hackerrank": coding.get("hackerrank"),
    }


def _week_blocks(entries: list[dict], weekly_hours: int) -> list[str]:
    blocks = []
    cursor = 1
    for e in entries:
        weeks_needed = max(1, round(e["effort_hours"] / weekly_hours)) if weekly_hours else 1
        end = cursor + weeks_needed - 1
        label = f"Weeks {cursor}-{end}" if weeks_needed > 1 else f"Week {cursor}"
        blocks.append(f"{label}   {e['category_name']} → level {e['target_level']}")
        cursor = end + 1
    return blocks


def _plan_section(talent_check: dict, plan: dict | None) -> str:
    gap_views = compute_gap_views(talent_check["skillset_gap"])
    gap_lookup = {g["category_code"]: g for g in talent_check["skillset_gap"]}

    if plan and plan.get("overrides"):
        from core.planning import effort_hours as _eh

        weekly_hours = plan.get("weekly_hours", WEEKLY_HOURS_DEFAULT)
        overrides = plan["overrides"]
        entries = []
        for code, target in overrides.items():
            g = gap_lookup.get(code)
            if not g:
                continue
            entries.append({
                "category_name": g["category_name"],
                "target_level": target,
                "effort_hours": _eh(code, max(0, target - g["candidate_level"])),
            })
        sim = simulate(talent_check, overrides, weekly_hours=weekly_hours)
        projected = f"{sim['baseline_readiness']} → {sim['new_readiness']}"
    else:
        weekly_hours = WEEKLY_HOURS_DEFAULT
        budget_hours = weekly_hours * 12
        entries = []
        overrides = {}
        running_hours = 0
        for row in gap_views["recommended"]:
            if running_hours >= budget_hours:
                break
            entries.append({
                "category_name": row["category_name"],
                "target_level": row["required_level"],
                "effort_hours": row["effort_hours"],
            })
            overrides[row["category_code"]] = row["required_level"]
            running_hours += row["effort_hours"]
        sim = simulate(talent_check, overrides, weekly_hours=weekly_hours)
        projected = f"{sim['baseline_readiness']} → {sim['new_readiness']}"

    if not entries:
        return "No significant gaps remain — there's no plan to build."

    lines = _week_blocks(entries, weekly_hours)
    lines.append(f"Projected readiness after: {projected}")
    return "\n".join(lines)


def generate_report(profile: dict, talent_check: dict, skill_match: dict,
                     company_rankings: list[dict], plan: dict | None = None) -> str:
    """Returns Markdown. Pure function — no file I/O."""
    name = profile.get("name") or "Candidate"
    company = talent_check.get("company", "")
    role = skill_match.get("role", "")
    readiness = talent_check.get("readiness_score", 0)
    match = skill_match.get("match_score", 0)
    verdict = talent_check.get("verdict", "")
    generated = datetime.date.today().strftime("%d %B %Y")

    gap_views = compute_gap_views(talent_check["skillset_gap"])
    strengths = _strengths(talent_check)
    evidence = _evidence_counts(profile)

    lines: list[str] = []
    lines.append("=" * 56)
    lines.append("  RADIX TALENT MATCH — READINESS REPORT")
    header_bits = [b for b in [name, company, role] if b]
    lines.append(f"  {' · '.join(header_bits)}")
    lines.append(f"  Generated {generated}")
    lines.append("=" * 56)
    lines.append("")

    # 1 · SUMMARY
    lines.append("## 1 · Summary")
    lines.append("")
    lines.append(f"**Company readiness**  {readiness} / 100  — {verdict}")
    lines.append(f"**Role fit**  {match} / 100  — {_match_band(match)}")
    lines.append("")
    diff = abs(readiness - match)
    if diff < 15:
        summary_note = (
            f"Your fit for this specific role tracks closely with your overall readiness for {company}. "
            f"Whatever you improve next will help both scores."
        )
    elif match > readiness:
        summary_note = (
            f"You're a stronger fit for this specific posting than for {company}'s general bar — "
            f"this role doesn't test everything the company overall does."
        )
    else:
        summary_note = (
            f"You're closer to being ready for {company} overall than for this exact posting — "
            f"the role tests some things your broader profile doesn't yet cover as strongly."
        )
    lines.append(summary_note)
    lines.append("")

    # 2 · STRENGTHS
    lines.append("## 2 · Your strengths")
    lines.append("")
    if strengths:
        for g in sorted(strengths, key=lambda g: -g["candidate_level"]):
            source_note = " (verified)" if g.get("level_source") == "verified" else ""
            lines.append(f"- **{g['category_name']}** — level {g['candidate_level']} / {g['required_level']} required{source_note}")
    else:
        lines.append("No skillset currently clears the required bar — the plan below is where to start.")
    lines.append("")

    # 3 · GAPS
    lines.append("## 3 · Your gaps")
    lines.append("")
    lines.append("| Category | Required | Yours | Gap | Est. effort |")
    lines.append("|---|---|---|---|---|")
    for row in gap_views["recommended"]:
        lines.append(
            f"| {row['category_name']} | {row['required_level']} | {row['candidate_level']} "
            f"| {row['gap_size']} | ~{row['effort_hours']} hrs |"
        )
    lines.append("")

    # 4 · WHERE TO FOCUS FIRST
    lines.append("## 4 · Where to focus first")
    lines.append("")
    for i, row in enumerate(gap_views["recommended"][:3], start=1):
        weeks = round(row["effort_hours"] / WEEKLY_HOURS_DEFAULT, 1)
        lines.append(f"**{i}. {row['category_name']}**")
        lines.append(f"- Estimated {row['effort_hours']} hours (~{weeks} weeks at {WEEKLY_HOURS_DEFAULT} hrs/week)")
        lines.append(f"- Recovers about {_fmt_pct(row['impact_points'])} readiness points")
        lines.append(f"- First step: work through a focused {row['category_name'].lower()} fundamentals track and build one small project that uses it.")
        lines.append("")

    # 5 · FOR THIS SPECIFIC ROLE
    lines.append("## 5 · For this specific role")
    lines.append("")
    missing = skill_match.get("missing_skills", [])
    if missing:
        for s in missing:
            lines.append(f"- {s['skill_name']} ({s['confidence']} confidence in the posting)")
    else:
        lines.append("No missing skills for this specific role.")
    lines.append("")

    # 6 · WHERE ELSE YOU'D FIT
    lines.append("## 6 · Where else you'd fit")
    lines.append("")
    if company_rankings:
        lines.append("| # | Company | Readiness | Verdict | Top gap |")
        lines.append("|---|---|---|---|---|")
        for i, row in enumerate(company_rankings[:10], start=1):
            lines.append(
                f"| {i} | {row['company']} | {row['readiness_score']} | {row['verdict']} | {row.get('top_gap') or '—'} |"
            )
    else:
        lines.append("No company comparison available.")
    lines.append("")

    # 7 · YOUR EVIDENCE
    lines.append("## 7 · Your evidence")
    lines.append("")
    lines.append(f"- Resume: {evidence['resume_count']} skills")
    lines.append(f"- Profile additions (self-reported): {evidence['manual_count']} skills")
    if evidence["leetcode"]:
        lc = evidence["leetcode"]
        lines.append(
            f"- LeetCode (verified): {lc.get('total_solved', 0)} solved"
            + (f", rating {lc['contest_rating']}" if lc.get("contest_rating") else "")
        )
    if evidence["hackerrank"]:
        hr = evidence["hackerrank"]
        lines.append(
            f"- HackerRank (verified): {hr.get('problem_solving_stars', 0)}-star Problem Solving, "
            f"{hr.get('language_stars', 0)}-star language track"
        )
    lines.append("")
    lines.append("Verified data was used wherever it was higher than the self-reported estimate.")
    lines.append("")

    # 8 · SUGGESTED 12-WEEK PLAN
    lines.append("## 8 · Suggested 12-week plan")
    lines.append("")
    lines.append(_plan_section(talent_check, plan))
    lines.append("")

    # 9 · HOW THESE NUMBERS WERE CALCULATED
    lines.append("## 9 · How these numbers were calculated")
    lines.append("")
    lines.append(CALC_EXPLANATION)

    return "\n".join(lines)


def _match_band(score: int) -> str:
    if score >= 85:
        return "Strong match"
    if score >= 70:
        return "Good match"
    if score >= 50:
        return "Partial match"
    return "Weak match"
