# agent.py — one command per resume. This is what the UiPath bot calls (R4).
#
#   python agent.py --resume "data/inbox/Priya Menon.pdf" `
#                   --jd "data/jds/Microsoft - Data Analyst.pdf" `
#                   --jd-folder data/jds `
#                   --summary "data/out/runs/Priya_Menon/summary.json" --quiet
#
# What it does:
#   1. runs the pipeline for the primary JD into data/out/runs/<stem>/primary/
#   2. if that would be a reject, re-scores the candidate against every OTHER
#      JD in --jd-folder, each into its own subfolder
#   3. asks modules/m6_screening_agent for the decision, and for a reroute
#   4. writes summary.json and (for reject/reroute) feedback.md via storage
#   5. appends one row to data/out/screening_log.csv
#   6. prints exactly one RESULT_JSON line; exit 0 on a decision, 1 on exception
#
# No traceback ever reaches stdout. Every failure becomes a structured result
# with decision "exception" and a readable reason.

import argparse
import datetime
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.extract_text import extract_text, guess_company_and_role
from core.storage import (append_log_row, load_jd_companies,
                          load_screening_config, rel_path, save_json, save_text)
from modules.m6_screening_agent import (SCORE_LABELS, decide, feedback_markdown,
                                        resolve_thresholds, reroute, score_for)
from pipeline import run_pipeline

RESULT_PREFIX = "RESULT_JSON "
RUNS_ROOT = "data/out/runs"
DOC_SUFFIXES = (".pdf", ".docx", ".txt", ".md")
# Both formats of each JD sit in data/jds; screen each posting once (resolution #6).
SUFFIX_PREFERENCE = {".pdf": 0, ".docx": 1, ".txt": 2, ".md": 3}

DECIDED_EXIT = 0
EXCEPTION_EXIT = 1


def _slug(text: str) -> str:
    """Folder-safe, space-free name. Sample files are called "Priya Menon.pdf",
    and a path with a space is a standing hazard in a UiPath argument."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_")
    return cleaned or "unnamed"


def _jd_candidates(folder: str) -> list[pathlib.Path]:
    """Every distinct posting in the folder, one file each, deterministic order."""
    root = pathlib.Path(folder)
    if not root.is_dir():
        return []
    best: dict[str, pathlib.Path] = {}
    for path in root.iterdir():
        if not path.is_file() or path.suffix.lower() not in DOC_SUFFIXES:
            continue
        current = best.get(path.stem)
        if current is None or (SUFFIX_PREFERENCE[path.suffix.lower()]
                               < SUFFIX_PREFERENCE[current.suffix.lower()]):
            best[path.stem] = path
    return [best[stem] for stem in sorted(best)]


def _company_and_role(jd_path: str, overrides: dict) -> tuple[str, str]:
    """Auto-detect, with config/jd_companies.json winning where it has an entry.
    A JD we cannot read yields ("", "") and the pipeline reports the stage error."""
    stem = pathlib.Path(jd_path).stem
    try:
        company, role = guess_company_and_role(extract_text(jd_path), jd_path)
    except Exception:
        company, role = "", ""
    override = overrides.get(stem)
    if isinstance(override, str) and override.strip():
        company = override.strip()
    return company, role


def _score_row(summary: dict, mode: str, thresholds: dict,
               primary: bool = False) -> dict:
    """One candidate-vs-one-JD row in the shape reroute() expects."""
    decision, _ = decide(summary.get("readiness"), summary.get("match"), thresholds)
    return {
        "role": summary.get("role", ""),
        "company": summary.get("company", ""),
        "score": score_for(summary.get("readiness"), summary.get("match"), mode),
        "decision": decision,
        "primary": primary,
        "readiness": summary.get("readiness"),
        "match": summary.get("match"),
    }


def screen_resume(resume_path: str, jd_path: str, jd_folder: str | None = None,
                  out_root: str = RUNS_ROOT, company_override: str | None = None,
                  thresholds: dict | None = None, quiet: bool = False) -> dict:
    """Screen one resume against one primary JD. Returns the summary record."""
    thresholds = resolve_thresholds(thresholds if thresholds is not None
                                    else load_screening_config())
    mode = thresholds["score"]
    overrides = load_jd_companies()
    run_dir = pathlib.Path(out_root) / _slug(pathlib.Path(resume_path).stem)

    def say(line: str) -> None:
        if not quiet:
            print(line)

    # 1 · primary JD
    company, role = _company_and_role(jd_path, overrides)
    if company_override:
        company = company_override
    say(f"· primary   {pathlib.Path(jd_path).stem}  ({company or 'company unknown'})")
    primary = run_pipeline(jd_path, resume_path, company,
                           out_dir=str(run_dir / "primary"), quiet=True)["summary"]
    if not primary.get("role"):
        primary["role"] = role

    summary = dict(primary)
    summary.update({"rerouted_to_role": "", "rerouted_to_company": "",
                    "rerouted_score": None, "feedback_file": ""})

    # 2 · decide
    if primary["stages_ok"] != 5:
        # pipeline already set decision "exception" and a reason naming the stage
        say(f"  -> exception: {primary['reason']}")
        return _finalise(summary, run_dir, resume_path, quiet)

    decision, reason = decide(primary["readiness"], primary["match"], thresholds)
    score = score_for(primary["readiness"], primary["match"], mode)
    summary["decision"], summary["reason"] = decision, reason
    say(f"  readiness {primary['readiness']} · match {primary['match']} "
        f"· {SCORE_LABELS[mode].lower()} {score} -> {decision}")

    # 3 · only a reject is worth re-scoring against the other open roles
    if decision == "reject" and jd_folder:
        primary_stem = pathlib.Path(jd_path).stem
        rows = [_score_row(primary, mode, thresholds, primary=True)]
        for alt_jd in _jd_candidates(jd_folder):
            if alt_jd.stem == primary_stem:
                continue
            alt_company, alt_role = _company_and_role(str(alt_jd), overrides)
            alt = run_pipeline(str(alt_jd), resume_path, alt_company,
                               out_dir=str(run_dir / f"alt_{_slug(alt_jd.stem)}"),
                               quiet=True)["summary"]
            if not alt.get("role"):
                alt["role"] = alt_role
            row = _score_row(alt, mode, thresholds)
            rows.append(row)
            say(f"· alt       {alt_jd.stem:40} score {str(row['score']):>4} "
                f"-> {row['decision']}")

        best = reroute(rows, primary["role"], thresholds["reroute_min_gain"])
        if best:
            summary["decision"] = "reroute"
            summary["reason"] = (
                f"{SCORE_LABELS[mode]} {score} for {primary['role']}, but "
                f"{best['role']} at {best['company']} scores {best['score']} "
                f"(+{best['gain']}) — a better fit for this candidate."
            )
            summary["rerouted_to_role"] = best["role"]
            summary["rerouted_to_company"] = best["company"]
            summary["rerouted_score"] = best["score"]
            say(f"  -> reroute: {best['role']} at {best['company']} "
                f"(score {best['score']}, +{best['gain']})")

    return _finalise(summary, run_dir, resume_path, quiet)


def _finalise(summary: dict, run_dir: pathlib.Path, resume_path: str,
              quiet: bool) -> dict:
    """4 + 5 — write feedback.md where it is owed, then append the audit row."""
    if summary["decision"] in ("reject", "reroute"):
        talent_check = _read_run_file(run_dir / "primary" / "talent_check_result.json")
        skill_match = _read_run_file(run_dir / "primary" / "skill_match_result.json")
        summary["feedback_file"] = save_text(
            str(run_dir / "feedback.md"),
            feedback_markdown(summary, talent_check, skill_match),
        )
        if not quiet:
            print(f"  feedback   {summary['feedback_file']}")

    row = dict(summary)
    row["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
    row["top_gaps"] = "; ".join(summary.get("top_gaps") or [])
    row["missing_skills"] = "; ".join(summary.get("missing_skills") or [])
    append_log_row(row)
    return summary


def _read_run_file(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _exception_summary(resume_path: str, message: str) -> dict:
    """Last line of defence: an unexpected failure still produces a structured
    result, never a traceback on stdout."""
    return {
        "resume_file": rel_path(resume_path), "candidate_name": "", "email": "",
        "company": "", "role": "", "readiness": None, "verdict": "", "match": None,
        "top_gaps": [], "missing_skills": [], "decision": "exception",
        "reason": f"The screening agent could not process this file: {message}",
        "stages_ok": 0, "error": message,
        "rerouted_to_role": "", "rerouted_to_company": "", "rerouted_score": None,
        "feedback_file": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Screen one resume and decide what happens to the candidate.")
    parser.add_argument("--resume", required=True, help="Path to the resume file")
    parser.add_argument("--jd", required=True, help="Path to the primary JD file")
    parser.add_argument("--jd-folder", default=None,
                        help="Folder of other open JDs to consider for a reroute")
    parser.add_argument("--company", default=None,
                        help="Override the auto-detected company for the primary JD")
    parser.add_argument("--out-root", default=RUNS_ROOT,
                        help=f"Root for per-resume run folders (default: {RUNS_ROOT})")
    parser.add_argument("--summary", default=None,
                        help="Write the summary record to this path as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Print only the RESULT_JSON line")
    args = parser.parse_args()

    try:
        summary = screen_resume(
            args.resume, args.jd, jd_folder=args.jd_folder, out_root=args.out_root,
            company_override=args.company, quiet=args.quiet,
        )
    except Exception as e:                      # noqa: BLE001 — rule 6
        summary = _exception_summary(args.resume, f"{type(e).__name__}: {e}")
        try:
            row = dict(summary)
            row["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
            append_log_row(row)
        except Exception:                        # noqa: BLE001 — logging must never fail the run
            pass

    # The written file and the printed line are byte-for-byte the same record.
    if args.summary:
        p = pathlib.Path(args.summary)
        save_json(p.name, summary, out_dir=str(p.parent))

    print(RESULT_PREFIX + json.dumps(summary, ensure_ascii=False))
    return DECIDED_EXIT if summary["decision"] != "exception" else EXCEPTION_EXIT


if __name__ == "__main__":
    sys.exit(main())
