# Orchestration layer — runs all 5 modules in order, records status, prints terminal ticks.
#
# R2 additions (RPA_AGENT_PROMPT §3):
#   - out_dir      : every save lands in a per-run folder instead of fixed data/out
#   - results["summary"] : one flat, HR-readable record of the whole run
#   - RESULT_JSON  : exactly one machine-readable line for UiPath to parse
#   - --quiet      : suppress the tick lines, print only RESULT_JSON
#   - exit code    : 0 if all 5 stages succeeded, 1 otherwise
#
# The pipeline scores. It does NOT choose an outcome — that is the screening
# agent's job (modules/m6_screening_agent.py, R3). The summary therefore carries
# decision "pending" on a clean run, and "exception" when a stage failed.

import argparse
import json
import pathlib
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.contract import CATEGORY_NAMES
from core.extract_text import extract_text, guess_company_and_role
from core.status import mark
from core.storage import load_company_data, rel_path, save_json
from modules.m1_jd_analytics import analyse_jd
from modules.m2_resume_parsing import parse_resume
from modules.m3_profile_builder import build_profile
from modules.m4_talent_check import run_talent_check
from modules.m5_skill_matching import match_skills

RESULT_PREFIX = "RESULT_JSON "
MAX_MISSING_SKILLS = 5


def build_summary(resume_path: str, company: str, results: dict,
                  stages_ok: int, errors: list[str]) -> dict:
    """Flatten the five payloads into one record. Pure data shaping — no
    thresholds, no file I/O, no clock."""
    resume_payload = results.get("resume_skills") or {}
    jd_payload = results.get("jd_skills") or {}
    talent_check = results.get("talent_check_result") or {}
    skill_match = results.get("skill_match_result") or {}

    top_gaps = [CATEGORY_NAMES.get(code, code) for code in talent_check.get("top_gaps", [])]
    missing = [s.get("skill_name", "") for s in skill_match.get("missing_skills", [])]

    if stages_ok == 5:
        decision = "pending"
        reason = "All 5 stages scored — the screening agent decides the outcome."
    else:
        decision = "exception"
        reason = f"Only {stages_ok}/5 stages completed: " + ("; ".join(errors) or "unknown failure")

    return {
        "resume_file": rel_path(resume_path),
        "candidate_name": resume_payload.get("candidate_name", ""),
        "email": resume_payload.get("email", ""),
        "company": company,
        "role": jd_payload.get("role", ""),
        "readiness": talent_check.get("readiness_score"),
        "verdict": talent_check.get("verdict", ""),
        "match": skill_match.get("match_score"),
        "top_gaps": top_gaps,
        "missing_skills": missing[:MAX_MISSING_SKILLS],
        "decision": decision,
        "reason": reason,
        "stages_ok": stages_ok,
        "error": "; ".join(errors),
    }


def run_pipeline(jd_path: str, resume_path: str, company: str,
                  profile_overrides: dict | None = None,
                  out_dir: str | None = None,
                  quiet: bool = False) -> dict:
    profile_overrides = profile_overrides or {}
    start = time.time()
    ok_count = 0
    errors: list[str] = []
    results = {}

    def say(line: str) -> None:
        if not quiet:
            print(line)

    # [1/5] JD Analytics
    jd_payload = None
    try:
        text = extract_text(jd_path)
        guessed_company, guessed_role = guess_company_and_role(text, jd_path)
        jd_payload = analyse_jd(
            text, pathlib.Path(jd_path).name, company=guessed_company, role=guessed_role
        )
        save_json("jd_skills.json", jd_payload, out_dir=out_dir)
        cats = len(set(s["category_code"] for s in jd_payload["skills"]))
        detail = f"{len(jd_payload['skills'])} skills across {cats} categories"
        mark("m1_jd_analytics", True, detail)
        say(f"[1/5] JD Analytics ......... ✅  {detail}")
        ok_count += 1
    except Exception as e:
        mark("m1_jd_analytics", False, str(e))
        errors.append(f"JD Analytics: {e}")
        say(f"[1/5] JD Analytics ......... ❌  {e}")
    results["jd_skills"] = jd_payload

    # [2/5] Resume Parsing
    resume_payload = None
    try:
        text = extract_text(resume_path)
        resume_payload = parse_resume(text, pathlib.Path(resume_path).name)
        save_json("resume_skills.json", resume_payload, out_dir=out_dir)
        detail = f"{len(resume_payload['skills'])} skills · {resume_payload['candidate_name']}"
        mark("m2_resume_parsing", True, detail)
        say(f"[2/5] Resume Parsing ....... ✅  {detail}")
        ok_count += 1
    except Exception as e:
        mark("m2_resume_parsing", False, str(e))
        errors.append(f"Resume Parsing: {e}")
        say(f"[2/5] Resume Parsing ....... ❌  {e}")
    results["resume_skills"] = resume_payload

    # [3/5] Profile Builder
    profile = None
    try:
        profile = build_profile(profile_overrides, resume_payload)
        save_json("profile.json", profile, out_dir=out_dir)
        detail = f"profile saved · {len(profile['skills'])} skills"
        mark("m3_profile_builder", True, detail)
        say(f"[3/5] Profile Builder ...... ✅  {detail}")
        ok_count += 1
    except Exception as e:
        mark("m3_profile_builder", False, str(e))
        errors.append(f"Profile Builder: {e}")
        say(f"[3/5] Profile Builder ...... ❌  {e}")
    results["profile"] = profile

    # [4/5] Talent Check — requires profile
    talent_check_result = None
    if profile is None:
        errors.append("Talent Check: skipped — requires Profile Builder")
        say("[4/5] Talent Check ......... ⏭️  skipped — requires Profile Builder")
    else:
        try:
            company_data = load_company_data()
            talent_check_result = run_talent_check(profile, company, company_data)
            save_json("talent_check_result.json", talent_check_result, out_dir=out_dir)
            detail = (
                f"{company} · readiness {talent_check_result['readiness_score']} "
                f"· {talent_check_result['verdict']}"
            )
            mark("m4_talent_check", True, detail)
            say(f"[4/5] Talent Check ......... ✅  {detail}")
            ok_count += 1
        except Exception as e:
            mark("m4_talent_check", False, str(e))
            errors.append(f"Talent Check: {e}")
            say(f"[4/5] Talent Check ......... ❌  {e}")
    results["talent_check_result"] = talent_check_result

    # [5/5] Skill Matching — requires profile and JD skills
    skill_match_result = None
    if profile is None or jd_payload is None:
        missing = "Profile Builder" if profile is None else "JD Analytics"
        errors.append(f"Skill Matching: skipped — requires {missing}")
        say(f"[5/5] Skill Matching ....... ⏭️  skipped — requires {missing}")
    else:
        try:
            skill_match_result = match_skills(profile, jd_payload)
            save_json("skill_match_result.json", skill_match_result, out_dir=out_dir)
            detail = (
                f"match {skill_match_result['match_score']} "
                f"· {len(skill_match_result['missing_skills'])} missing skills"
            )
            mark("m5_skill_matching", True, detail)
            say(f"[5/5] Skill Matching ....... ✅  {detail}")
            ok_count += 1
        except Exception as e:
            mark("m5_skill_matching", False, str(e))
            errors.append(f"Skill Matching: {e}")
            say(f"[5/5] Skill Matching ....... ❌  {e}")
    results["skill_match_result"] = skill_match_result

    results["summary"] = build_summary(resume_path, company, results, ok_count, errors)

    elapsed = time.time() - start
    if not quiet:
        print()
        print(f"PIPELINE COMPLETE · {ok_count}/5 · {elapsed:.1f}s")
    return results


def _write_summary(summary: dict, summary_path: str) -> str:
    """storage.py owns the write (rule 4) — this only splits the path."""
    p = pathlib.Path(summary_path)
    return save_json(p.name, summary, out_dir=str(p.parent))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the RADIX Talent Match pipeline end to end.")
    parser.add_argument("--jd", required=True, help="Path to the JD file (PDF/DOCX/TXT)")
    parser.add_argument("--resume", required=True, help="Path to the resume file (PDF/DOCX/TXT)")
    parser.add_argument("--company", required=True, help="Exact company name as it appears in the dataset")
    parser.add_argument("--out-dir", default=None,
                        help="Per-run output folder (default: data/out)")
    parser.add_argument("--summary", default=None,
                        help="Write the summary record to this path as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress the tick lines — print only the RESULT_JSON line")
    args = parser.parse_args()

    results = run_pipeline(args.jd, args.resume, args.company,
                           out_dir=args.out_dir, quiet=args.quiet)
    summary = results["summary"]

    if args.summary:
        _write_summary(summary, args.summary)

    print(RESULT_PREFIX + json.dumps(summary, ensure_ascii=False))
    sys.exit(0 if summary["stages_ok"] == 5 else 1)
