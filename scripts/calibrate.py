# R5 — threshold calibration.
#
# Real match scores in this project are low (PROGRESS M17 records 11-34). Fixed
# cutoffs like 70 would reject every candidate, which is exactly what R4's first
# run showed. This script scores every sample resume against every sample JD,
# prints the actual distribution, and proposes thresholds that split the samples
# into shortlist / review / reject instead of flattening them into one bucket.
#
#   python scripts/calibrate.py                 # report only
#   python scripts/calibrate.py --apply         # also write config/screening.json
#
# Scoring logic is untouched — this only chooses where the lines sit.

import argparse
import pathlib
import statistics
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent import _company_and_role, _jd_candidates, _slug          # noqa: E402
from core.storage import (SCREENING_CONFIG_PATH, load_jd_companies,  # noqa: E402
                          load_screening_config, save_json)
from modules.m6_screening_agent import (DEFAULT_THRESHOLDS, decide,  # noqa: E402
                                        resolve_thresholds, reroute, score_for)
from pipeline import run_pipeline                                    # noqa: E402

RESUME_SUFFIXES = (".pdf", ".docx", ".txt", ".md")
CALIBRATION_OUT = "data/out/calibration"
SUFFIX_PREFERENCE = {".pdf": 0, ".docx": 1, ".txt": 2, ".md": 3}


def _resume_candidates(folder: str) -> list[pathlib.Path]:
    """One file per candidate, .pdf preferred — the folder holds both formats."""
    root = pathlib.Path(folder)
    if not root.is_dir():
        return []
    best: dict[str, pathlib.Path] = {}
    for path in root.iterdir():
        if not path.is_file() or path.suffix.lower() not in RESUME_SUFFIXES:
            continue
        current = best.get(path.stem)
        if current is None or (SUFFIX_PREFERENCE[path.suffix.lower()]
                               < SUFFIX_PREFERENCE[current.suffix.lower()]):
            best[path.stem] = path
    return [best[stem] for stem in sorted(best)]


def score_matrix(resume_folder: str, jd_folder: str) -> list[dict]:
    """Every resume against every JD. One pipeline run per cell."""
    overrides = load_jd_companies()
    resumes = _resume_candidates(resume_folder)
    jds = _jd_candidates(jd_folder)
    print(f"Scoring {len(resumes)} resumes x {len(jds)} JDs = "
          f"{len(resumes) * len(jds)} pipeline runs...\n")

    cells = []
    for resume in resumes:
        for jd in jds:
            company, role = _company_and_role(str(jd), overrides)
            summary = run_pipeline(
                str(jd), str(resume), company,
                out_dir=f"{CALIBRATION_OUT}/{_slug(resume.stem)}/{_slug(jd.stem)}",
                quiet=True,
            )["summary"]
            cells.append({
                "resume": resume.stem,
                "jd": jd.stem,
                "company": company,
                "role": summary.get("role") or role,
                "readiness": summary.get("readiness"),
                "match": summary.get("match"),
                "stages_ok": summary.get("stages_ok"),
            })
    return cells


def _average(cell: dict) -> int | None:
    return score_for(cell["readiness"], cell["match"], "average")


def print_matrix(cells: list[dict]) -> None:
    jds = sorted({c["jd"] for c in cells})
    resumes = sorted({c["resume"] for c in cells})
    lookup = {(c["resume"], c["jd"]): c for c in cells}

    print("SCORE MATRIX — readiness / match / average")
    print()
    width = max(len(r) for r in resumes) + 2
    for jd in jds:
        print(f"  {jd}")
        print(f"    {'resume':<{width}} {'readiness':>9} {'match':>6} {'average':>8}")
        for resume in resumes:
            c = lookup[(resume, jd)]
            print(f"    {resume:<{width}} {str(c['readiness']):>9} "
                  f"{str(c['match']):>6} {str(_average(c)):>8}")
        print()


def _stats(values: list[int]) -> dict:
    values = sorted(v for v in values if isinstance(v, int))
    if not values:
        return {}
    out = {
        "n": len(values),
        "min": values[0],
        "max": values[-1],
        "median": statistics.median(values),
    }
    if len(values) >= 3:
        lo, hi = statistics.quantiles(values, n=3)
        out["p33"], out["p67"] = round(lo), round(hi)
    return out


def print_distribution(cells: list[dict]) -> dict:
    print("DISTRIBUTION across every resume x JD pair")
    print()
    series = {
        "readiness": [c["readiness"] for c in cells],
        "match": [c["match"] for c in cells],
        "average": [_average(c) for c in cells],
    }
    print(f"  {'series':<10} {'n':>3} {'min':>5} {'median':>7} {'max':>5} "
          f"{'p33':>5} {'p67':>5}")
    computed = {}
    for name, values in series.items():
        s = _stats(values)
        computed[name] = s
        print(f"  {name:<10} {s['n']:>3} {s['min']:>5} {s['median']:>7} {s['max']:>5} "
              f"{s.get('p33', '-'):>5} {s.get('p67', '-'):>5}")
    print()
    return computed


def print_reroute_potential(cells: list[dict], primary_jd_stem: str,
                            thresholds: dict) -> None:
    """How much a candidate can gain by moving to another open role — this is
    what reroute_min_gain has to be small enough to allow."""
    print(f"REROUTE POTENTIAL — primary posting: {primary_jd_stem}")
    print()
    mode = thresholds["score"]
    by_resume: dict[str, list[dict]] = {}
    for c in cells:
        by_resume.setdefault(c["resume"], []).append(c)

    print(f"  {'resume':<22} {'primary':>8} {'best alt':>9} {'gain':>5}  best alternative role")
    for resume in sorted(by_resume):
        rows = []
        primary_score = None
        for c in by_resume[resume]:
            decision, _ = decide(c["readiness"], c["match"], thresholds)
            score = score_for(c["readiness"], c["match"], mode)
            is_primary = c["jd"] == primary_jd_stem
            if is_primary:
                primary_score = score
            rows.append({"role": c["role"], "company": c["company"], "score": score,
                         "decision": decision, "primary": is_primary})
        primary_role = next((r["role"] for r in rows if r["primary"]), "")
        others = [r for r in rows if not r["primary"] and isinstance(r["score"], int)]
        best = max(others, key=lambda r: r["score"]) if others else None
        gain = (best["score"] - primary_score) if (best and primary_score is not None) else None
        chosen = reroute(rows, primary_role, thresholds["reroute_min_gain"])
        label = f"{best['role']} @ {best['company']}" if best else "-"
        flag = "  <- reroute fires" if chosen else ""
        print(f"  {resume:<22} {str(primary_score):>8} {str(best['score'] if best else '-'):>9} "
              f"{str(gain):>5}  {label}{flag}")
    print()


def suggest(dist: dict, cells: list[dict], primary_jd_stem: str,
            mode: str) -> dict:
    """Terciles of the observed distribution, then checked against the primary
    posting's own column — the lines have to split the demo, not just the data."""
    s = dist[mode]
    shortlist_at = s["p67"]
    review_at = s["p33"]

    primary_scores = sorted(
        score_for(c["readiness"], c["match"], mode)
        for c in cells if c["jd"] == primary_jd_stem
        and isinstance(score_for(c["readiness"], c["match"], mode), int)
    )
    # The demo must show all three outcomes on the primary posting. If the
    # tercile cut does not achieve that, fall back to splitting that column.
    buckets = {
        "shortlist" if v >= shortlist_at else "review" if v >= review_at else "reject"
        for v in primary_scores
    }
    if len(buckets) < 3 and len(primary_scores) >= 3:
        shortlist_at = primary_scores[-1]
        review_at = primary_scores[len(primary_scores) // 2]

    # Smallest gain that lets a rejected candidate reach their BEST alternative.
    # reroute() always picks the highest-scoring eligible role, so the weaker
    # alternatives' gains are irrelevant — using them would set the bar far too
    # low and send people to roles that only just clear the review line.
    gains = []
    by_resume: dict[str, list[dict]] = {}
    for c in cells:
        by_resume.setdefault(c["resume"], []).append(c)
    for rows in by_resume.values():
        primary = next((r for r in rows if r["jd"] == primary_jd_stem), None)
        if primary is None:
            continue
        ps = score_for(primary["readiness"], primary["match"], mode)
        if ps is None or ps >= review_at:
            continue                     # not a reject, so nothing to reroute
        eligible = [
            s for r in rows if r["jd"] != primary_jd_stem
            for s in [score_for(r["readiness"], r["match"], mode)]
            if s is not None and s >= review_at and s > ps
        ]
        if eligible:
            gains.append(max(eligible) - ps)
    reroute_min_gain = min(gains) if gains else DEFAULT_THRESHOLDS["reroute_min_gain"]

    return {
        "shortlist_at": int(shortlist_at),
        "review_at": int(review_at),
        "reroute_min_gain": int(reroute_min_gain),
        "score": mode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate the screening thresholds.")
    parser.add_argument("--resume-folder", default="data/resumes")
    parser.add_argument("--jd-folder", default="data/jds")
    parser.add_argument("--primary-jd", default="Microsoft - Data Analyst",
                        help="JD filename stem the demo table is built on")
    parser.add_argument("--score", default=None, choices=("average", "readiness", "match"),
                        help="Score mode to calibrate (default: whatever the config says)")
    parser.add_argument("--apply", action="store_true",
                        help=f"Write the suggestion to {SCREENING_CONFIG_PATH}")
    args = parser.parse_args()

    current = resolve_thresholds(load_screening_config())
    mode = args.score or current["score"]

    cells = score_matrix(args.resume_folder, args.jd_folder)
    print_matrix(cells)
    dist = print_distribution(cells)
    print_reroute_potential(cells, args.primary_jd, current)

    proposed = suggest(dist, cells, args.primary_jd, mode)
    print("CURRENT  ", {k: current[k] for k in proposed})
    print("PROPOSED ", proposed)
    print()
    print(f"  Reasoning: on {dist[mode]['n']} resume x JD pairs the {mode} score runs "
          f"{dist[mode]['min']}-{dist[mode]['max']} (median {dist[mode]['median']}).")
    print(f"  shortlist_at {proposed['shortlist_at']} / review_at {proposed['review_at']} "
          f"splits that range into three populated bands instead of one.")
    print()

    print(f"DECISIONS ON THE PRIMARY POSTING ({args.primary_jd}) WITH THE PROPOSAL")
    print()
    print(f"  {'resume':<22} {'readiness':>9} {'match':>6} {'score':>6}  decision")
    seen = set()
    for c in sorted((c for c in cells if c["jd"] == args.primary_jd),
                    key=lambda c: c["resume"]):
        decision, _ = decide(c["readiness"], c["match"], proposed)
        seen.add(decision)
        print(f"  {c['resume']:<22} {str(c['readiness']):>9} {str(c['match']):>6} "
              f"{str(score_for(c['readiness'], c['match'], mode)):>6}  {decision}")
    print()
    print(f"  distinct decisions: {len(seen)} -> {sorted(seen)}")
    print()

    if args.apply:
        path = save_json(pathlib.Path(SCREENING_CONFIG_PATH).name, proposed,
                         out_dir=str(pathlib.Path(SCREENING_CONFIG_PATH).parent))
        print(f"written -> {path}")
    else:
        print(f"report only. Re-run with --apply to write {SCREENING_CONFIG_PATH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
