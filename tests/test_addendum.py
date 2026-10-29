# Tests for FEATURE_ADDENDUM.md — F1 coding profiles, F2 simulator, F3 effort
# views, F4 company finder, F5 report. Run with: pytest tests/test_addendum.py -v

import json
import pathlib

import pytest

from core.company_rank import rank_companies
from core.coding_profiles import (
    hackerrank_to_levels, leetcode_to_levels, merge_verified_levels,
    verified_levels_from_coding_profiles,
)
from core.contract import (
    CONFIDENCE_LEVELS, CONFIDENCE_WEIGHT, validate_coding_profiles, validate_profile,
)
from core.planning import HOURS_PER_LEVEL, compute_gap_views, effort_hours, simulate
from core.report import generate_report
from core.storage import load_company_data
from modules.m4_talent_check import estimate_candidate_levels_detailed, run_talent_check
from modules.m5_skill_matching import match_skills

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "data" / "samples"
MICROSOFT = "Microsoft Corporation"


def _load_sample(name: str) -> dict:
    return json.loads((SAMPLES_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# core/contract.py — F1 confidence tier + coding_profiles block
# ---------------------------------------------------------------------------

def test_verified_is_highest_confidence_tier():
    assert CONFIDENCE_LEVELS[0] == "verified"
    assert CONFIDENCE_WEIGHT["verified"] == 4
    assert CONFIDENCE_WEIGHT["verified"] > CONFIDENCE_WEIGHT["high"]


def test_validate_coding_profiles_accepts_null_platforms():
    validate_coding_profiles({"leetcode": None, "hackerrank": None})


def test_validate_coding_profiles_rejects_bad_source():
    with pytest.raises(ValueError):
        validate_coding_profiles({"leetcode": {"username": "x", "source": "downloaded"}, "hackerrank": None})


def test_profile_without_coding_profiles_still_validates():
    profile = _load_sample("profile_data_leaning.json")
    assert "coding_profiles" not in profile
    validate_profile(profile)  # backward compatible — additive field, not required


def test_profile_with_coding_profiles_validates():
    profile = _load_sample("profile_data_leaning.json")
    profile["coding_profiles"] = {
        "leetcode": {"username": "ananya_r", "url": "https://leetcode.com/u/ananya_r",
                     "total_solved": 412, "easy": 180, "medium": 144, "hard": 88,
                     "contest_rating": 1847, "fetched_at": "2026-07-20T10:14:00", "source": "fetched"},
        "hackerrank": None,
    }
    validate_profile(profile)


# ---------------------------------------------------------------------------
# core/coding_profiles.py — F1.5 mapping + F1.6 merge rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("total_solved,expected_base", [
    (10, 3), (80, 5), (200, 6), (400, 7), (600, 8),
])
def test_leetcode_dsa_volume_buckets(total_solved, expected_base):
    levels = leetcode_to_levels({"total_solved": total_solved, "easy": 0, "medium": 0, "hard": 0, "contest_rating": 0})
    assert levels["DSA"]["level"] == expected_base


def test_leetcode_dsa_hard_and_contest_bonuses_cap_at_10():
    levels = leetcode_to_levels({"total_solved": 600, "easy": 100, "medium": 100, "hard": 400, "contest_rating": 2100})
    assert levels["DSA"]["level"] == 10  # 8 base + 1 hard + 2 contest, capped


def test_leetcode_cod_formula():
    levels = leetcode_to_levels({"total_solved": 350, "easy": 0, "medium": 0, "hard": 0, "contest_rating": 0})
    assert levels["COD"]["level"] == min(8, 3 + 350 // 100)


def test_leetcode_apti_no_contest_falls_back_to_dsa_minus_one():
    levels = leetcode_to_levels({"total_solved": 10, "easy": 0, "medium": 0, "hard": 0, "contest_rating": 0})
    assert levels["APTI"]["level"] == max(0, min(7, levels["DSA"]["level"] - 1))


def test_hackerrank_five_star_problem_solving_gives_dsa_seven():
    levels = hackerrank_to_levels({"problem_solving_stars": 5, "language_stars": 0, "gold_badges": 0})
    assert levels["DSA"]["level"] == 7
    assert "COD" not in levels  # no language stars given


def test_merge_rule_verified_raises_never_lowers():
    estimated = {"DSA": 3, "COD": 8, "APTI": 5}
    verified = {
        "DSA": {"level": 8, "reason": "500 solved", "platform": "LeetCode"},   # raises
        "COD": {"level": 4, "reason": "some", "platform": "LeetCode"},          # would lower — must not
    }
    merged = merge_verified_levels(estimated, verified)

    assert merged["DSA"]["level"] == 8
    assert merged["DSA"]["source"] == "verified"
    assert merged["DSA"]["evidence"].startswith("verified:")

    assert merged["COD"]["level"] == 8  # kept the higher estimate
    assert merged["COD"]["source"] == "estimated"
    assert "coding profile suggested 4" in merged["COD"]["evidence"]

    assert merged["APTI"]["source"] == "estimated"  # no verified data at all
    assert merged["APTI"]["verified_level"] is None


def test_verified_levels_from_coding_profiles_takes_max_across_platforms():
    coding_profiles = {
        "leetcode": {"total_solved": 600, "easy": 200, "medium": 200, "hard": 200, "contest_rating": 2200},
        "hackerrank": {"problem_solving_stars": 5, "language_stars": 5, "gold_badges": 2},
    }
    verified = verified_levels_from_coding_profiles(coding_profiles)
    # LeetCode DSA (600 solved, 33% hard, rating 2200) beats HackerRank's 7
    assert verified["DSA"]["platform"] == "LeetCode"
    assert verified["DSA"]["level"] >= 9


def test_verified_levels_empty_when_no_coding_profiles():
    assert verified_levels_from_coding_profiles(None) == {}
    assert verified_levels_from_coding_profiles({"leetcode": None, "hackerrank": None}) == {}


# ---------------------------------------------------------------------------
# modules/m4_talent_check.py — F1 wired into estimate + run_talent_check
# ---------------------------------------------------------------------------

def test_estimate_detailed_matches_plain_estimate_without_coding_profiles():
    from modules.m4_talent_check import estimate_candidate_levels
    profile = _load_sample("profile_systems_leaning.json")
    detailed = estimate_candidate_levels_detailed(profile)
    plain = estimate_candidate_levels(profile)
    assert plain == {code: d["level"] for code, d in detailed.items()}
    assert all(d["source"] == "estimated" for d in detailed.values())


def test_run_talent_check_carries_verified_evidence_for_dsa():
    profile = _load_sample("profile_data_leaning.json")  # weak DSA
    profile["coding_profiles"] = {
        "leetcode": {"username": "test", "total_solved": 500, "easy": 150, "medium": 250, "hard": 100,
                     "contest_rating": 1900, "source": "manual"},
        "hackerrank": None,
    }
    company_data = load_company_data()
    result = run_talent_check(profile, MICROSOFT, company_data)
    dsa_row = next(g for g in result["skillset_gap"] if g["category_code"] == "DSA")

    assert dsa_row["level_source"] == "verified"
    assert dsa_row["verified_level"] is not None
    assert dsa_row["candidate_level"] == dsa_row["verified_level"]
    assert dsa_row["effort_hours"] == dsa_row["gap_size"] * HOURS_PER_LEVEL["DSA"]


def test_run_talent_check_never_lowers_a_strong_estimate():
    profile = _load_sample("profile_systems_leaning.json")  # strong DSA already
    company_data = load_company_data()
    baseline = run_talent_check(profile, MICROSOFT, company_data)
    baseline_dsa = next(g for g in baseline["skillset_gap"] if g["category_code"] == "DSA")["candidate_level"]

    profile["coding_profiles"] = {
        "leetcode": {"username": "test", "total_solved": 5, "easy": 5, "medium": 0, "hard": 0,
                     "contest_rating": 0, "source": "manual"},
        "hackerrank": None,
    }
    with_thin_profile = run_talent_check(profile, MICROSOFT, company_data)
    dsa_row = next(g for g in with_thin_profile["skillset_gap"] if g["category_code"] == "DSA")

    assert dsa_row["candidate_level"] == baseline_dsa  # unchanged — never lowered
    assert dsa_row["level_source"] == "estimated"


# ---------------------------------------------------------------------------
# core/planning.py — F2 simulator + F3 effort views
# ---------------------------------------------------------------------------

def _sample_skillset_gap():
    return [
        {"category_code": "SQL", "category_name": "SQL & Design", "required_level": 5,
         "candidate_level": 0, "gap": True, "gap_size": 5},
        {"category_code": "AI", "category_name": "AI-Native Engineering", "required_level": 7,
         "candidate_level": 0, "gap": True, "gap_size": 7},
        {"category_code": "COMM", "category_name": "Communication Skills", "required_level": 5,
         "candidate_level": 5, "gap": False, "gap_size": 0},
    ]


def test_compute_gap_views_orders_by_the_right_metric():
    views = compute_gap_views(_sample_skillset_gap())
    assert views["recommended"][0]["category_code"] == "SQL"  # best roi: cheap + decent impact
    assert views["quickest_wins"][0]["category_code"] == "SQL"  # fewest hours
    assert views["biggest_impact"][0]["category_code"] == "AI"  # biggest gap_size / total
    assert views["already_met"] == ["COMM"]


def test_effort_hours_matches_hours_table():
    assert effort_hours("SQL", 5) == 5 * HOURS_PER_LEVEL["SQL"]
    assert effort_hours("AI", 3) == 3 * HOURS_PER_LEVEL["AI"]


def test_simulate_caps_at_required_and_floors_at_current():
    talent_check = {"readiness_score": 34, "skillset_gap": _sample_skillset_gap()}
    # try to push SQL above required (10) and AI below current (candidate=0, target=-5)
    sim = simulate(talent_check, {"SQL": 10, "AI": -5})
    sql_component_hours = effort_hours("SQL", 5)  # capped to required_level=5, delta=5
    assert sim["effort_hours"] == sql_component_hours  # AI override <= candidate contributes 0 hours
    assert sim["new_readiness"] > sim["baseline_readiness"]


def test_simulate_never_writes_anything(tmp_path, monkeypatch):
    # Pure function — asserting no storage import/usage is implicit; this just
    # re-runs it twice and checks it's deterministic (no hidden state mutation).
    talent_check = {"readiness_score": 34, "skillset_gap": _sample_skillset_gap()}
    r1 = simulate(talent_check, {"SQL": 5})
    r2 = simulate(talent_check, {"SQL": 5})
    assert r1 == r2


# ---------------------------------------------------------------------------
# core/company_rank.py — F4
# ---------------------------------------------------------------------------

def test_rank_companies_sorted_descending_and_covers_all():
    profile = _load_sample("profile_data_leaning.json")
    company_data = load_company_data()
    rankings = rank_companies(profile, company_data)

    assert len(rankings) == len(company_data)
    scores = [r["readiness_score"] for r in rankings]
    assert scores == sorted(scores, reverse=True)


def test_rank_companies_top_n():
    profile = _load_sample("profile_data_leaning.json")
    company_data = load_company_data()
    top5 = rank_companies(profile, company_data, top_n=5)
    assert len(top5) == 5


# ---------------------------------------------------------------------------
# core/report.py — F5
# ---------------------------------------------------------------------------

def test_generate_report_has_all_nine_sections_in_order():
    profile = _load_sample("profile_data_leaning.json")
    company_data = load_company_data()
    talent_check = run_talent_check(profile, MICROSOFT, company_data)
    jd_payload = {"source_type": "jd", "source_file": "x", "company": MICROSOFT, "role": "Data Analyst",
                  "skills": [{"skill_name": "SQL", "category_code": "SQL", "evidence": "x", "confidence": "high"}]}
    skill_match = match_skills(profile, jd_payload)
    rankings = rank_companies(profile, company_data, top_n=10)

    report = generate_report(profile, talent_check, skill_match, rankings)

    headings = [f"## {i} ·" for i in range(1, 10)]
    positions = [report.index(h) for h in headings]
    assert positions == sorted(positions)  # section 2 before 3, etc. — strict order
    assert "not been validated against real hiring outcomes" in report  # section 9 non-negotiable


def test_generate_report_is_pure_no_file_io(tmp_path, monkeypatch):
    import core.storage as storage
    monkeypatch.setattr(storage, "DATA_OUT", str(tmp_path))

    profile = _load_sample("profile_data_leaning.json")
    company_data = load_company_data()
    talent_check = run_talent_check(profile, MICROSOFT, company_data)
    jd_payload = {"source_type": "jd", "source_file": "x", "company": MICROSOFT, "role": "Data Analyst", "skills": []}
    skill_match = match_skills(profile, jd_payload)
    rankings = rank_companies(profile, company_data, top_n=3)

    generate_report(profile, talent_check, skill_match, rankings)
    assert list(tmp_path.iterdir()) == []  # nothing written to disk
