# Smoke tests covering module contracts, the two required differentiation checks
# (Talent Check across candidates, Skill Matching across JDs), and failure paths.
# Run with: pytest tests/test_smoke.py -v

import json
import pathlib

import pytest

from core.contract import ALL_CODES, CATEGORY_CODES, validate_profile, validate_skill_list
from core.extract_text import extract_text
from core.skill_dictionary import extract_skills
from core.storage import load_company_data, load_json
from modules.m1_jd_analytics import analyse_jd
from modules.m2_resume_parsing import parse_resume
from modules.m3_profile_builder import build_profile, prefill_from_resume
from modules.m4_talent_check import run_talent_check
from modules.m5_skill_matching import match_skills
from pipeline import run_pipeline

ROOT = pathlib.Path(__file__).resolve().parents[1]
JD_DIR = ROOT / "data" / "jds"
RESUME_DIR = ROOT / "data" / "resumes"
SAMPLES_DIR = ROOT / "data" / "samples"

MICROSOFT = "Microsoft Corporation"
GOOGLE = "Google LLC (Subsidiary of Alphabet Inc.)"
ORACLE = "Oracle Financial Services Software Limited"


# ---------------------------------------------------------------------------
# core/contract.py
# ---------------------------------------------------------------------------

def test_contract_code_counts():
    assert len(CATEGORY_CODES) == 12
    assert len(ALL_CODES) == 13
    assert "OTHER" in ALL_CODES
    assert "OTHER" not in CATEGORY_CODES


def test_validate_skill_rejects_bad_category():
    from core.contract import validate_skill
    with pytest.raises(ValueError):
        validate_skill({
            "skill_name": "Python", "category_code": "NOT_A_CODE",
            "evidence": "x", "confidence": "high",
        })


def test_normalise_skill_name_aliases():
    from core.contract import normalise_skill_name
    assert normalise_skill_name("JS") == "javascript"
    assert normalise_skill_name("Power BI") == "powerbi"
    assert normalise_skill_name("  SQL  ") == "sql"


# ---------------------------------------------------------------------------
# core/skill_dictionary.py
# ---------------------------------------------------------------------------

def test_extract_skills_finds_expected_categories():
    skills = extract_skills("We need Python, SQL and Kubernetes")
    codes = {s["category_code"] for s in skills}
    assert {"COD", "SQL", "CLOUD"}.issubset(codes)


def test_extract_skills_empty_text():
    assert extract_skills("") == []


# ---------------------------------------------------------------------------
# core/storage.py + company data
# ---------------------------------------------------------------------------

def test_company_data_loads_and_has_12_codes():
    data = load_company_data()
    assert len(data) >= 90
    ms = data[MICROSOFT]["skillsets"]
    assert len(ms) == 12
    assert set(ms.keys()).issubset(set(CATEGORY_CODES))


def test_storage_round_trip(tmp_path, monkeypatch):
    import core.storage as storage
    monkeypatch.setattr(storage, "DATA_OUT", str(tmp_path))
    path = storage.save_json("_rt.json", {"a": 1})
    assert pathlib.Path(path).exists()
    assert storage.load_json("_rt.json") == {"a": 1}
    assert storage.load_json("_missing.json") is None


# ---------------------------------------------------------------------------
# modules/m1_jd_analytics.py
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", [
    "Google LLC - Software Engineer.pdf",
    "Microsoft - Data Analyst.pdf",
    "Oracle - Associate Software Engineer.pdf",
])
def test_analyse_jd_meets_minimum_bar(filename):
    text = extract_text(str(JD_DIR / filename))
    result = analyse_jd(text, filename)
    validate_skill_list(result)
    categories = {s["category_code"] for s in result["skills"]}
    assert len(result["skills"]) >= 8
    assert len(categories) >= 4


# ---------------------------------------------------------------------------
# modules/m2_resume_parsing.py
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected_name", [
    ("Ananya Rao.pdf", "Ananya Rao"),
    ("Rohan Verma.docx", "Rohan Verma"),
])
def test_parse_resume_extracts_skills_and_name(filename, expected_name):
    text = extract_text(str(RESUME_DIR / filename))
    result = parse_resume(text, filename)
    validate_skill_list(result)
    assert len(result["skills"]) > 0
    assert result["candidate_name"] == expected_name
    assert any(result["structured"].values())


# ---------------------------------------------------------------------------
# modules/m3_profile_builder.py
# ---------------------------------------------------------------------------

def test_build_profile_merges_without_duplicates():
    text = extract_text(str(RESUME_DIR / "Rohan Verma.pdf"))
    resume_payload = parse_resume(text, "Rohan Verma.pdf")
    prefill = prefill_from_resume(resume_payload)
    dup_name = prefill["skills"][0]["skill_name"]

    profile = build_profile(
        {"manual_skills": [{"skill_name": dup_name, "category_code": prefill["skills"][0]["category_code"]}]},
        resume_payload,
    )
    validate_profile(profile)
    names = [s["skill_name"] for s in profile["skills"]]
    assert names.count(dup_name) == 1


# ---------------------------------------------------------------------------
# modules/m4_talent_check.py — the required differentiation check (M12)
# ---------------------------------------------------------------------------

def test_talent_check_scores_differ_across_candidates():
    company_data = load_company_data()
    systems = json.loads((SAMPLES_DIR / "profile_systems_leaning.json").read_text(encoding="utf-8"))
    data_leaning = json.loads((SAMPLES_DIR / "profile_data_leaning.json").read_text(encoding="utf-8"))

    r1 = run_talent_check(systems, MICROSOFT, company_data)
    r2 = run_talent_check(data_leaning, MICROSOFT, company_data)

    assert abs(r1["readiness_score"] - r2["readiness_score"]) >= 15


def test_talent_check_unknown_company_no_crash():
    profile = json.loads((SAMPLES_DIR / "profile_data_leaning.json").read_text(encoding="utf-8"))
    result = run_talent_check(profile, "Totally Fake Company Inc", {})
    assert result["readiness_score"] == 0
    assert result["skillset_gap"] == []


# ---------------------------------------------------------------------------
# modules/m5_skill_matching.py — the required differentiation check (M14)
# ---------------------------------------------------------------------------

def test_skill_match_scores_differ_across_jds():
    profile = json.loads((SAMPLES_DIR / "profile_data_leaning.json").read_text(encoding="utf-8"))

    jd1_text = extract_text(str(JD_DIR / "Microsoft - Data Analyst.pdf"))
    jd1 = analyse_jd(jd1_text, "Microsoft - Data Analyst.pdf")
    jd2_text = extract_text(str(JD_DIR / "Oracle - Application Support Analyst.pdf"))
    jd2 = analyse_jd(jd2_text, "Oracle - Application Support Analyst.pdf")

    r1 = match_skills(profile, jd1)
    r2 = match_skills(profile, jd2)

    assert r1["match_score"] != r2["match_score"]


def test_skill_match_empty_jd_no_division_by_zero():
    profile = {"skills": [{"skill_name": "Python", "category_code": "COD", "evidence": "x", "confidence": "high"}]}
    jd_payload = {"source_type": "jd", "source_file": "x", "company": "", "role": "", "skills": []}
    result = match_skills(profile, jd_payload)
    assert result["match_score"] == 0
    assert "message" in result


# ---------------------------------------------------------------------------
# pipeline.py — end to end, all three in-scope companies
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("jd_file,resume_file,company", [
    ("Microsoft - Data Analyst.pdf", "Priya Menon.pdf", MICROSOFT),
    ("Oracle - Associate Software Engineer.pdf", "Rohan Verma.pdf", ORACLE),
    ("Google LLC - Software Engineer.pdf", "Ananya Rao.pdf", GOOGLE),
])
def test_pipeline_end_to_end(jd_file, resume_file, company):
    results = run_pipeline(str(JD_DIR / jd_file), str(RESUME_DIR / resume_file), company)

    for key in ("jd_skills", "resume_skills", "profile", "talent_check_result", "skill_match_result"):
        assert results[key] is not None, f"{key} was not produced"

    validate_skill_list(results["jd_skills"])
    validate_skill_list(results["resume_skills"])
    validate_profile(results["profile"])
    assert results["talent_check_result"]["company"] == company
    assert 0 <= results["talent_check_result"]["readiness_score"] <= 100
    assert 0 <= results["skill_match_result"]["match_score"] <= 100

    for filename in ("jd_skills.json", "resume_skills.json", "profile.json",
                      "talent_check_result.json", "skill_match_result.json"):
        assert load_json(filename) is not None


def test_pipeline_missing_jd_file_does_not_crash():
    results = run_pipeline(
        str(JD_DIR / "does_not_exist.pdf"), str(RESUME_DIR / "Priya Menon.pdf"), MICROSOFT
    )
    assert results["jd_skills"] is None
    assert results["skill_match_result"] is None  # skipped — requires JD Analytics
    assert results["resume_skills"] is not None
    assert results["profile"] is not None
    assert results["talent_check_result"] is not None


# ---------------------------------------------------------------------------
# core/extract_text.py — failure path
# ---------------------------------------------------------------------------

def test_extract_text_unsupported_extension_raises(tmp_path):
    bad_file = tmp_path / "resume.xyz"
    bad_file.write_text("hello")
    with pytest.raises(ValueError):
        extract_text(str(bad_file))
