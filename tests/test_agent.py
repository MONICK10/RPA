# Tests for the RPA / agent layer (RPA_AGENT_PROMPT §4).
#
# R3 covers modules/m6_screening_agent.py: decide, reroute, feedback_markdown.
# The agent.py CLI tests arrive with R4.

import json
import pathlib
import re
import subprocess
import sys

import pytest

from core.contract import ALL_CODES
from core.storage import SCREENING_LOG_PATH, load_screening_config
from modules.m6_screening_agent import (DEFAULT_THRESHOLDS, decide,
                                        feedback_markdown, reroute,
                                        resolve_thresholds, score_for)

T = {"shortlist_at": 60, "review_at": 40, "reroute_min_gain": 10, "score": "average"}


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def test_screening_config_file_loads_with_the_four_expected_keys():
    cfg = load_screening_config()
    assert set(cfg) == {"shortlist_at", "review_at", "reroute_min_gain", "score"}
    assert cfg["score"] in ("average", "readiness", "match")


def test_resolve_thresholds_fills_gaps_and_ignores_junk():
    assert resolve_thresholds(None) == DEFAULT_THRESHOLDS
    assert resolve_thresholds({})["shortlist_at"] == 60
    # unknown score mode and a non-numeric cutoff both fall back
    bad = resolve_thresholds({"score": "vibes", "shortlist_at": "high"})
    assert bad["score"] == "average" and bad["shortlist_at"] == 60
    # an inverted band is clamped, never left to create a dead branch
    clamped = resolve_thresholds({"shortlist_at": 50, "review_at": 80})
    assert clamped["review_at"] == 50


# ---------------------------------------------------------------------------
# decide — every branch
# ---------------------------------------------------------------------------

def test_decide_shortlist():
    decision, reason = decide(72, 61, T)
    assert decision == "shortlist"
    assert "66" in reason and "60" in reason


def test_decide_review():
    decision, reason = decide(57, 34, T)
    assert decision == "review"
    # the worked example from the prompt: average 45, between 40 and 60
    assert reason.startswith("Average fit 45 —")
    assert "needs a human look" in reason


def test_decide_reject():
    decision, reason = decide(28, 11, T)
    assert decision == "reject"
    assert "19" in reason and "40" in reason


@pytest.mark.parametrize("readiness,match", [
    (None, 34),
    (57, None),
    (None, None),
])
def test_decide_exception_when_a_score_is_missing(readiness, match):
    decision, reason = decide(readiness, match, T)
    assert decision == "exception"
    assert "could not be scored" in reason


# ---------------------------------------------------------------------------
# decide — ties exactly on each threshold
# ---------------------------------------------------------------------------

def test_decide_tie_exactly_on_shortlist_threshold_is_shortlist():
    # average of 60 and 60 is exactly 60
    assert decide(60, 60, T)[0] == "shortlist"


def test_decide_one_point_below_shortlist_is_review():
    assert decide(60, 58, T)[0] == "review"      # average 59


def test_decide_tie_exactly_on_review_threshold_is_review():
    assert decide(40, 40, T)[0] == "review"


def test_decide_one_point_below_review_is_reject():
    assert decide(40, 38, T)[0] == "reject"      # average 39


def test_decide_zero_scores_are_a_reject_not_an_exception():
    # 0 is a real score; only a missing score is an exception
    assert decide(0, 0, T)[0] == "reject"


# ---------------------------------------------------------------------------
# score modes
# ---------------------------------------------------------------------------

def test_score_modes_pick_different_numbers():
    assert score_for(57, 34, "average") == 45     # floor, matches the spec example
    assert score_for(57, 34, "readiness") == 57
    assert score_for(57, 34, "match") == 34


def test_readiness_mode_ignores_a_missing_match():
    decision, _ = decide(72, None, {**T, "score": "readiness"})
    assert decision == "shortlist"


def test_match_mode_ignores_a_missing_readiness():
    decision, _ = decide(None, 11, {**T, "score": "match"})
    assert decision == "reject"


# ---------------------------------------------------------------------------
# reroute
# ---------------------------------------------------------------------------

PRIMARY = {"role": "Data Analyst", "company": "Microsoft Corporation",
           "score": 19, "decision": "reject", "primary": True}


def test_reroute_returns_none_when_there_is_no_alternative():
    assert reroute([PRIMARY], "Data Analyst", 10) is None


def test_reroute_returns_none_when_the_alternative_is_below_min_gain():
    rows = [PRIMARY,
            {"role": "Software Engineer", "company": "Google LLC",
             "score": 27, "decision": "reject"}]
    # 27 - 19 = 8, under a min gain of 10
    assert reroute(rows, "Data Analyst", 10) is None


def test_reroute_returns_none_when_the_alternative_does_not_reach_review():
    rows = [PRIMARY,
            {"role": "Software Engineer", "company": "Google LLC",
             "score": 39, "decision": "reject"}]
    # gain of 20 clears min_gain, but a "reject" is not somewhere to send anyone
    assert reroute(rows, "Data Analyst", 10) is None


def test_reroute_returns_the_valid_alternative():
    rows = [PRIMARY,
            {"role": "Software Engineer", "company": "Google LLC",
             "score": 48, "decision": "review"}]
    best = reroute(rows, "Data Analyst", 10)
    assert best["role"] == "Software Engineer"
    assert best["company"] == "Google LLC"
    assert best["score"] == 48
    assert best["gain"] == 29


def test_reroute_picks_the_highest_scoring_eligible_alternative():
    rows = [PRIMARY,
            {"role": "Application Support Analyst", "company": "Oracle", "score": 44,
             "decision": "review"},
            {"role": "Software Engineer", "company": "Google LLC", "score": 61,
             "decision": "shortlist"},
            {"role": "Data Scientist", "company": "Google LLC", "score": 52,
             "decision": "review"}]
    assert reroute(rows, "Data Analyst", 10)["role"] == "Software Engineer"


def test_reroute_breaks_a_score_tie_deterministically():
    rows = [PRIMARY,
            {"role": "Zebra Engineer", "company": "Zoho", "score": 50, "decision": "review"},
            {"role": "Alpha Engineer", "company": "Acko", "score": 50, "decision": "review"}]
    # same score twice — role name decides, so repeated runs never differ
    assert reroute(rows, "Data Analyst", 10)["role"] == "Alpha Engineer"
    assert reroute(list(reversed(rows)), "Data Analyst", 10)["role"] == "Alpha Engineer"


def test_reroute_returns_none_when_the_primary_role_is_not_in_the_list():
    rows = [{"role": "Software Engineer", "company": "Google LLC",
             "score": 61, "decision": "shortlist"}]
    assert reroute(rows, "Data Analyst", 10) is None


def test_reroute_excludes_the_primary_role_at_another_company():
    rows = [PRIMARY,
            {"role": "data analyst", "company": "Oracle", "score": 70, "decision": "shortlist"}]
    # same role, different company: a reroute has to be a different ROLE
    assert reroute(rows, "Data Analyst", 10) is None


# ---------------------------------------------------------------------------
# feedback_markdown
# ---------------------------------------------------------------------------

TALENT_CHECK = {
    "company": "Microsoft Corporation",
    "readiness_score": 24,
    "verdict": "Significant gaps",
    "skillset_gap": [
        {"category_code": "DSA", "category_name": "Data Structures & Algorithms",
         "required_level": 8, "candidate_level": 0, "gap": True, "gap_size": 8},
        {"category_code": "COD", "category_name": "Coding",
         "required_level": 7, "candidate_level": 7, "gap": False, "gap_size": 0},
        {"category_code": "SQL", "category_name": "SQL & Design",
         "required_level": 6, "candidate_level": 1, "gap": True, "gap_size": 5},
        {"category_code": "AI", "category_name": "AI-Native Engineering",
         "required_level": 7, "candidate_level": 0, "gap": True, "gap_size": 7},
        {"category_code": "OS", "category_name": "Operating Systems",
         "required_level": 5, "candidate_level": 6, "gap": False, "gap_size": 0},
    ],
    "top_gaps": ["DSA", "AI", "SQL"],
}

SKILL_MATCH = {
    "match_score": 15,
    "matched_skills": [{"jd_skill": "Python", "profile_skill": "Python", "how": "exact"}],
    "missing_skills": [
        {"skill_name": "Power BI", "category_code": "SQL", "confidence": "high"},
        {"skill_name": "Stakeholder", "category_code": "COMM", "confidence": "medium"},
    ],
    "category_coverage": {"SQL": 0.5},
}

SUMMARY = {"candidate_name": "Priya Menon", "role": "Data Analyst",
           "company": "Microsoft Corporation", "decision": "reject"}

# Codes that have no innocent reading in candidate-facing prose. "AI" and
# "SQL" are excluded here because they are also genuine skill names a JD can
# name (Section D #14) — the separate test below proves neither is ever used
# as a CATEGORY LABEL.
OPAQUE_CODES = [c for c in ALL_CODES if c not in ("AI", "SQL")]

JSON_FIELD_NAMES = [
    "category_code", "category_name", "gap_size", "required_level",
    "candidate_level", "skillset_gap", "readiness_score", "match_score",
    "missing_skills", "matched_skills", "top_gaps", "candidate_name",
    "category_coverage", "source_type", "source_file", "skill_name",
    "stages_ok", "rerouted_to_role",
]


def test_feedback_contains_no_opaque_category_codes():
    text = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    for code in OPAQUE_CODES:
        assert not re.search(rf"\b{code}\b", text), f"category code {code} leaked to the candidate"


def test_feedback_never_uses_ai_or_sql_as_a_category_label():
    text = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    # both categories are in the fixture and both are gaps, so both are rendered
    assert "Machine learning" in text
    assert "Databases and data modelling" in text
    assert "AI-Native Engineering" not in text
    assert "SQL & Design" not in text


def test_feedback_contains_no_json_field_names():
    text = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    for field in JSON_FIELD_NAMES:
        assert field not in text, f"JSON field name {field} leaked to the candidate"


def test_feedback_leads_with_strengths_then_gaps():
    text = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    assert text.index("What's already working") < text.index("holding you back most")
    assert "Coding" in text              # the met category
    assert "Operating Systems" in text


def test_feedback_names_at_most_three_gaps_worst_first():
    text = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    assert "1. **Data Structures & Algorithms**" in text   # gap 8
    assert "2. **Machine learning**" in text               # gap 7
    assert "3. **Databases and data modelling**" in text   # gap 5
    assert "4. " not in text


def test_feedback_lists_the_missing_jd_skills():
    text = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    assert "- Power BI" in text
    assert "- Stakeholder" in text


def test_feedback_closing_changes_with_the_decision():
    reject = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    rerouted = feedback_markdown(
        {**SUMMARY, "decision": "reroute", "rerouted_to_role": "Software Engineer",
         "rerouted_to_company": "Google LLC"}, TALENT_CHECK, SKILL_MATCH)
    assert "isn't the right fit right now" in reject
    assert "Software Engineer at Google LLC" in rerouted


def test_feedback_survives_empty_inputs_without_raising():
    text = feedback_markdown({}, {}, {})
    assert text.startswith("# Where you stand")
    assert "Nothing. Every skill this posting names" in text


def test_feedback_is_deterministic():
    a = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    b = feedback_markdown(SUMMARY, TALENT_CHECK, SKILL_MATCH)
    assert a == b


# ---------------------------------------------------------------------------
# agent.py — the CLI UiPath calls (R4)
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESUME_DIR = ROOT / "data" / "resumes"
PRIMARY_JD = ROOT / "data" / "jds" / "Microsoft - Data Analyst.pdf"


def run_agent(resume: str, out_root: pathlib.Path, summary: pathlib.Path,
              jd_folder: str | None = None):
    """Invoke the real CLI the way UiPath will — a separate process."""
    cmd = [sys.executable, "agent.py", "--resume", resume, "--jd", str(PRIMARY_JD),
           "--out-root", str(out_root), "--summary", str(summary), "--quiet"]
    if jd_folder:
        cmd += ["--jd-folder", jd_folder]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def result_json(proc) -> dict:
    lines = [l for l in proc.stdout.splitlines() if l.startswith("RESULT_JSON ")]
    assert len(lines) == 1, f"expected exactly one RESULT_JSON line, got {len(lines)}"
    return json.loads(lines[0][len("RESULT_JSON "):])


def test_agent_on_a_good_resume_exits_0_and_decides(tmp_path):
    proc = run_agent(str(RESUME_DIR / "Priya Menon.pdf"), tmp_path / "runs",
                     tmp_path / "summary.json")
    summary = result_json(proc)
    assert proc.returncode == 0
    assert summary["decision"] in ("shortlist", "review", "reject", "reroute")
    assert summary["stages_ok"] == 5
    assert summary["candidate_name"] == "Priya Menon"


def test_agent_on_an_unreadable_file_exits_1_with_no_traceback(tmp_path):
    unreadable = tmp_path / "scan.pdf"
    unreadable.write_bytes(b"")                      # deliberately unreadable
    proc = run_agent(str(unreadable), tmp_path / "runs", tmp_path / "summary.json")
    summary = result_json(proc)

    assert proc.returncode == 1
    assert summary["decision"] == "exception"
    assert summary["reason"]                          # a readable reason, not blank
    assert "Traceback" not in proc.stdout
    assert "Traceback" not in proc.stderr


def test_agent_writes_a_summary_file_matching_the_printed_line(tmp_path):
    out = tmp_path / "summary.json"
    proc = run_agent(str(RESUME_DIR / "Rohan Verma.pdf"), tmp_path / "runs", out)
    assert json.loads(out.read_text(encoding="utf-8")) == result_json(proc)


def test_agent_writes_feedback_for_a_reject_or_reroute(tmp_path):
    proc = run_agent(str(RESUME_DIR / "Priya Menon.pdf"), tmp_path / "runs",
                     tmp_path / "summary.json")
    summary = result_json(proc)
    if summary["decision"] in ("reject", "reroute"):
        assert summary["feedback_file"]
        assert (ROOT / summary["feedback_file"]).exists()
    else:
        assert summary["feedback_file"] == ""


def test_two_runs_on_different_resumes_do_not_overwrite_each_other(tmp_path):
    runs = tmp_path / "runs"
    a = run_agent(str(RESUME_DIR / "Priya Menon.pdf"), runs, tmp_path / "a.json")
    b = run_agent(str(RESUME_DIR / "Rohan Verma.pdf"), runs, tmp_path / "b.json")
    sa, sb = result_json(a), result_json(b)

    assert sa["candidate_name"] == "Priya Menon"
    assert sb["candidate_name"] == "Rohan Verma"
    assert sa != sb
    # separate per-resume folders, each with its own five stage outputs
    assert (runs / "Priya_Menon" / "primary" / "talent_check_result.json").exists()
    assert (runs / "Rohan_Verma" / "primary" / "talent_check_result.json").exists()
    assert json.loads((tmp_path / "a.json").read_text(encoding="utf-8")) == sa
    assert json.loads((tmp_path / "b.json").read_text(encoding="utf-8")) == sb


def test_agent_is_deterministic_across_runs(tmp_path):
    runs = tmp_path / "runs"
    first = tmp_path / "1.json"
    second = tmp_path / "2.json"
    # same out-root both times — the real "re-run the inbox" case
    run_agent(str(RESUME_DIR / "Ananya Rao.pdf"), runs, first, jd_folder="data/jds")
    run_agent(str(RESUME_DIR / "Ananya Rao.pdf"), runs, second, jd_folder="data/jds")
    # byte-identical summaries: no clock, no ordering wobble in the JD sweep
    assert first.read_bytes() == second.read_bytes()
    # and the per-stage outputs underneath are identical too
    for name in ("talent_check_result.json", "skill_match_result.json"):
        assert (runs / "Ananya_Rao" / "primary" / name).exists()


def test_log_csv_is_bom_prefixed_so_excel_and_uipath_decode_it(tmp_path):
    import csv

    from core.storage import append_log_row

    log = tmp_path / "screening_log.csv"
    reason = "Average fit 19 — below the review line (40)."
    append_log_row({"resume_file": "a.pdf", "reason": reason}, log_path=str(log))
    append_log_row({"resume_file": "b.pdf", "reason": reason}, log_path=str(log))

    raw = log.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "header must carry the UTF-8 BOM"
    assert raw.count(b"\xef\xbb\xbf") == 1, "BOM must not be written again on append"

    with log.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["reason"] == reason          # em-dash survives the round trip


# ---------------------------------------------------------------------------
# R6 - demo data and the reset/run harness
# ---------------------------------------------------------------------------

SEED_DIR = ROOT / "data" / "inbox_seed"
DECISION_FOLDERS = ("Shortlisted", "Review", "Rerouted", "Rejected", "Exceptions")


def test_inbox_seed_holds_four_resumes_and_one_unscreenable_file():
    from core.storage import list_files

    names = list_files(str(SEED_DIR))
    assert len(names) == 5, names
    readable = [n for n in names if n.lower().endswith((".pdf", ".docx", ".txt"))]
    assert len(readable) == 4
    # exactly one file the pipeline cannot read, so Exceptions is always demoed
    assert len(names) - len(readable) == 1


def test_the_unscreenable_seed_file_fails_with_a_readable_reason():
    from core.extract_text import extract_text
    from core.storage import list_files

    bad = [n for n in list_files(str(SEED_DIR))
           if not n.lower().endswith((".pdf", ".docx", ".txt"))]
    with pytest.raises(Exception) as excinfo:
        extract_text(str(SEED_DIR / bad[0]))
    # a sentence a non-technical HR user could act on, not a stack trace
    assert "Unsupported file type" in str(excinfo.value)


def test_uipath_decision_folders_all_exist():
    for folder in DECISION_FOLDERS:
        assert (ROOT / "data" / "uipath" / folder).is_dir(), folder


def test_storage_file_helpers_round_trip(tmp_path):
    from core.storage import (clear_dir, copy_file, delete_file, list_files,
                              move_file)

    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "a.txt").write_text("a", encoding="utf-8")
    (src / "b.txt").write_text("b", encoding="utf-8")

    assert list_files(str(src)) == ["a.txt", "b.txt"]
    assert list_files(str(tmp_path / "nope")) == []

    copy_file(str(src / "a.txt"), str(dst))
    assert list_files(str(dst)) == ["a.txt"]
    assert list_files(str(src)) == ["a.txt", "b.txt"]        # copy, not move

    move_file(str(src / "b.txt"), str(dst))
    assert list_files(str(dst)) == ["a.txt", "b.txt"]
    assert list_files(str(src)) == ["a.txt"]                 # move, not copy

    # copy_file overwrites in place rather than delete-then-write
    (src / "a.txt").write_text("changed", encoding="utf-8")
    copy_file(str(src / "a.txt"), str(dst))
    assert (dst / "a.txt").read_text(encoding="utf-8") == "changed"

    assert delete_file(str(dst / "a.txt")) is True
    assert delete_file(str(dst / "a.txt")) is False          # already gone

    (dst / "keep").mkdir()
    (dst / ".gitkeep").write_text("", encoding="utf-8")
    assert clear_dir(str(dst)) == 2                          # b.txt + keep/
    assert list_files(str(dst)) == []
    assert (dst / ".gitkeep").exists()                       # placeholder kept


def test_reset_dry_run_changes_nothing(tmp_path):
    """The reset is destructive, so --dry-run has to be genuinely inert."""
    inbox = tmp_path / "inbox"
    seed = tmp_path / "seed"
    seed.mkdir()
    inbox.mkdir()
    (seed / "one.pdf").write_text("seed", encoding="utf-8")
    (inbox / "stray.pdf").write_text("stray", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/reset_demo.py", "--dry-run",
         "--inbox", str(inbox), "--seed", str(seed),
         "--runs", str(tmp_path / "runs"), "--calibration", str(tmp_path / "cal"),
         "--uipath", str(tmp_path / "uipath")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DRY RUN" in proc.stdout
    # the stray is still there and the seed file was never copied in
    assert [p.name for p in inbox.iterdir()] == ["stray.pdf"]


def test_reset_refuses_to_clear_the_inbox_without_a_seed(tmp_path):
    """Without this guard a missing seed would wipe the demo data for good."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "precious.pdf").write_text("x", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/reset_demo.py",
         "--inbox", str(inbox), "--seed", str(tmp_path / "missing_seed"),
         "--runs", str(tmp_path / "runs"), "--calibration", str(tmp_path / "cal"),
         "--uipath", str(tmp_path / "uipath")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    assert proc.returncode == 1
    assert "refusing to clear" in proc.stdout
    assert (inbox / "precious.pdf").exists()


def test_agent_appends_exactly_one_log_row_per_resume(tmp_path):
    log = ROOT / SCREENING_LOG_PATH
    before = len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0
    run_agent(str(RESUME_DIR / "Karthik Subramaniam.pdf"), tmp_path / "runs",
              tmp_path / "summary.json")
    after = len(log.read_text(encoding="utf-8").splitlines())
    # one data row, plus the header if the log did not exist yet
    assert after - before in (1, 2)
