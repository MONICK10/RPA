# Streamlit UI — 3-screen candidate journey (Upload -> Profile -> Results),
# plus a Developer view (sidebar toggle) exposing the original 6-tab module
# view. Per UI_SPEC.md: the five modules, the data contract, and the scoring
# logic are untouched. This file only changes what the user sees.

import html
import json
import pathlib
import time

import pandas as pd
import streamlit as st

from core import llm
from core.coding_profiles import (
    fetch_hackerrank, fetch_leetcode, manual_hackerrank_stats, manual_leetcode_stats,
)
from core.company_rank import rank_companies
from core.contract import ALL_CODES, CATEGORY_NAMES, validate_profile
from core.extract_text import extract_text, guess_company_and_role
from core.planning import compute_gap_views, simulate
from core.report import generate_report
from core.status import get_status, mark, reset_status, summary_line
from core.storage import DATA_OUT, load_company_data, load_json, save_json
from modules.m1_jd_analytics import analyse_jd
from modules.m2_resume_parsing import parse_resume
from modules.m3_profile_builder import build_profile, prefill_from_resume
from modules.m4_talent_check import estimate_candidate_levels_detailed, run_talent_check
from modules.m5_skill_matching import match_skills
from pipeline import run_pipeline

st.set_page_config(page_title="RADIX Talent Match", page_icon="🎯", layout="wide")

UPLOAD_DIR = pathlib.Path("data/out/uploads")
JD_DIR = pathlib.Path("data/jds")
RESUME_DIR = pathlib.Path("data/resumes")
SUPPORTED_EXT = (".pdf", ".docx", ".txt")

# ---------------------------------------------------------------------------
# Global CSS — the RADIX/talencia palette from UI_SPEC.md §3.
# ---------------------------------------------------------------------------

FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700'
    '&family=Geist+Mono:wght@400;500&family=Instrument+Serif&display=swap" rel="stylesheet">'
)

CSS = """
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stToolbarActions"] { display: none; }
[data-testid="stAppDeployButton"] { display: none; }
[data-testid="stDecoration"] { display: none; }

:root {
    /* surfaces */
    --bg:          #0B0E14;
    --surface:     #141922;
    --surface-2:   #1C2230;
    --border:      #262E3D;

    /* text */
    --text:        #E6EAF2;
    --text-mute:   #8A94A6;
    --text-faint:  #5A6478;

    /* accent — RADIX amber, used sparingly */
    --accent:      #F0A030;
    --accent-dim:  #3A2C18;

    /* semantic */
    --good:        #3DD68C;
    --good-dim:    #123324;
    --warn:        #F5C451;
    --warn-dim:    #362B10;
    --bad:         #F0665C;
    --bad-dim:     #34181A;

    /* data viz */
    --bar-track:   #232B3A;
    --bar-req:     #4A5568;
    --bar-cand:    #F0A030;

    /* legacy aliases — existing rx-* components keep working unchanged */
    --navy-900: var(--text);
    --navy-700: var(--text-mute);
    --amber-500: var(--accent);
    --amber-600: #D68A22;
    --amber-100: var(--accent-dim);
    --paper: var(--bg);
    --green-600: var(--good);
    --green-100: var(--good-dim);
    --orange-600: var(--warn);
    --red-600: var(--bad);
    --red-100: var(--bad-dim);
}

html, body, [class*="css"] {
    font-family: 'Geist', -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

.rx-serif { font-family: 'Instrument Serif', Georgia, serif !important; }
.rx-mono { font-family: 'Geist Mono', ui-monospace, monospace !important; font-variant-numeric: tabular-nums; }

[data-testid="stAppViewContainer"] { background: var(--bg); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }

.block-container { max-width: 1120px; padding-top: 2rem; padding-bottom: 4rem; }

h1, h2, h3, h4 { color: var(--text); font-weight: 650; letter-spacing: -0.2px; }
/* the screen-1 page title wraps to two lines at 1120px — hold it to a
   readable measure and tighten the leading so the wrap looks deliberate */
.rx-page-title { max-width: 28ch; line-height: 1.15; margin-bottom: 0.25rem; }
p, li, label, div { color: var(--text); }
.rx-mute { color: var(--text-mute); font-size: 13px; }
.rx-faint { color: var(--text-faint); font-size: 12.5px; }
.rx-body { font-size: 15px; line-height: 1.6; color: var(--text); }

.rx-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
}
.rx-section-gap { margin-top: 2rem; }

.rx-eyebrow {
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text-faint);
}

div.stButton > button {
    border-radius: 6px; font-weight: 600; padding: 0.5rem 1.4rem; border: 1px solid var(--border);
    background: var(--surface-2); color: var(--text);
}
div.stButton > button[kind="primary"] { background: var(--amber-500); border: none; color: #0B0E14; }
div.stButton > button[kind="primary"]:hover { background: var(--amber-600); color: #0B0E14; }
div.stButton > button:disabled { background: var(--surface-2); color: var(--text-faint); border-color: var(--border); }

.rx-stepper { display: flex; align-items: flex-start; justify-content: center; max-width: 460px; margin: 0 auto 2.5rem auto; }
.rx-step-item { display: flex; flex-direction: column; align-items: center; gap: 8px; width: 100px; }
.rx-circle { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; }
.rx-circle.done { background: var(--amber-500); color: #FFFFFF; }
.rx-circle.active { background: var(--amber-500); color: #FFFFFF; box-shadow: 0 0 0 4px var(--amber-100); }
.rx-circle.locked { background: var(--surface); border: 2px solid var(--border); color: var(--text-mute); }
.rx-step-label { font-size: 13px; font-weight: 600; color: var(--text-mute); }
.rx-step-label.done, .rx-step-label.active { color: var(--navy-900); }
.rx-line { flex: 1 1 auto; height: 2px; background: var(--border); margin-top: 15px; }
.rx-line.done { background: var(--amber-500); }

[data-testid="stFileUploaderDropzone"] { border: 2px dashed var(--border) !important; border-radius: 12px !important; background: var(--surface) !important; }
.rx-dropzone-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.rx-dropzone-icon { font-size: 22px; }
.rx-dropzone-filled { border: 2px solid var(--green-600); border-radius: 12px; padding: 1.5rem; text-align: center; background: var(--green-100); }
.rx-dropzone-filled .tick { font-size: 26px; }
.rx-dropzone-filled .fname { font-weight: 700; color: var(--navy-900); margin-top: 4px; }

.rx-progress-line { font-size: 14px; color: var(--text-mute); padding: 5px 0; }
.rx-progress-line.done { color: var(--navy-900); }
.rx-progress-line b { color: var(--green-600); font-weight: 700; }

.rx-chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 14px 0; align-items: center; }
.rx-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.rx-chip-high { background: var(--amber-100); color: var(--navy-900); border: 1px solid transparent; }
.rx-chip-medium { background: transparent; border: 1px solid var(--navy-700); color: var(--navy-700); }
.rx-chip-low { background: transparent; border: 1px dashed var(--border); color: var(--text-mute); }
.rx-chip-met { background: var(--green-100); color: var(--green-600); }
.rx-chip-gap { background: var(--red-100); color: var(--red-600); }
.rx-chip-cat-label { font-size: 13px; font-weight: 600; color: var(--text-mute); min-width: 130px; display: inline-block; }

/* hero score cards — step 2 */
.rx-hero-pair { display: flex; gap: 20px; }
.rx-hero-card { flex: 1 1 0; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 24px; }
.rx-hero-numeral { font-size: 72px; line-height: 1; margin-top: 6px; }
.rx-hero-divider { height: 1px; background: var(--border); margin: 14px 0; width: 64px; }
.rx-hero-band { font-size: 15px; font-weight: 600; }
.rx-hero-sub { font-size: 12.5px; color: var(--text-mute); margin-top: 8px; line-height: 1.5; }

/* gap bars — step 3. One filled bar = the candidate; the vertical tick is the bar to clear. */
.rx-bar-row { display: flex; align-items: center; gap: 12px; padding: 7px 0; }
.rx-bar-label { width: 220px; font-size: 14px; color: var(--text); flex-shrink: 0; }
.rx-bar-label.met { color: var(--text-mute); }
.rx-bar-track { flex: 1 1 auto; height: 8px; background: var(--bar-track); border-radius: 4px; position: relative; overflow: visible; }
.rx-bar-fill { height: 8px; border-radius: 4px; background: var(--bar-cand); }
.rx-bar-marker { position: absolute; top: -4px; width: 2px; height: 16px; background: var(--bar-req); }
.rx-bar-value { width: 90px; font-size: 13px; color: var(--text-mute); text-align: right; flex-shrink: 0; }
.rx-bar-value.warn { color: var(--warn); }
.rx-bar-value.bad { color: var(--bad); }
.rx-bar-value.met { color: var(--good); }
.rx-bar-flag { color: var(--accent); font-weight: 700; }
</style>
"""

st.markdown(FONT_LINK, unsafe_allow_html=True)
st.markdown(CSS, unsafe_allow_html=True)

if "step" not in st.session_state:
    st.session_state.step = 1


# ---------------------------------------------------------------------------
# Shared: persistent stepper (spec §2)
# ---------------------------------------------------------------------------

def render_stepper() -> None:
    step = st.session_state.step

    def state(n):
        if step > n:
            return "done"
        if step == n:
            return "active"
        return "locked"

    def circle(n, label):
        s = state(n)
        glyph = "✓" if s == "done" else str(n)
        return f'<div class="rx-step-item"><div class="rx-circle {s}">{glyph}</div><div class="rx-step-label {s}">{label}</div></div>'

    def line(n):
        return f'<div class="rx-line {"done" if step > n else ""}"></div>'

    st.markdown(
        f'<div class="rx-stepper">{circle(1, "Upload")}{line(1)}{circle(2, "Profile")}{line(2)}{circle(3, "Results")}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _save_upload(uploaded_file, subdir: pathlib.Path) -> str:
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / uploaded_file.name
    path.write_bytes(uploaded_file.getvalue())
    return str(path)


def _sample_files(directory: pathlib.Path) -> list[str]:
    return sorted(p.name for p in directory.glob("*") if p.suffix.lower() in SUPPORTED_EXT)


def _band_color(score: int) -> str:
    if score >= 85:
        return "#3DD68C"
    if score >= 70:
        return "#F0A030"
    if score >= 50:
        return "#F5C451"
    return "#F0665C"


def _match_band_label(score: int) -> str:
    if score >= 85:
        return "Strong match"
    if score >= 70:
        return "Good match"
    if score >= 50:
        return "Partial match"
    return "Weak match"


def _hero_score_card(eyebrow: str, score: int, color: str, band: str, sub_html: str) -> str:
    """Hand-built hero score card (spec Part C.3) — no chart library, no ring.
    A big Instrument Serif numeral is the highest-leverage design choice here:
    it reads as a verdict, not a dashboard metric."""
    return (
        f'<div class="rx-hero-card">'
        f'<div class="rx-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="rx-hero-numeral rx-serif" style="color:{color};">{score}</div>'
        f'<div class="rx-hero-divider"></div>'
        f'<div class="rx-hero-band" style="color:{color};">{html.escape(band)}</div>'
        f'<div class="rx-hero-sub">{sub_html}</div>'
        f'</div>'
    )


# ===========================================================================
# Screen 1 · Upload
# ===========================================================================

def _dropzone(state_key: str, icon: str, title: str, directory: pathlib.Path, key_prefix: str) -> dict | None:
    selection = st.session_state.get(state_key)

    with st.container(border=True):
        if selection:
            st.markdown(
                f'''<div class="rx-dropzone-filled">
                    <div class="tick">✅</div>
                    <div class="fname">{html.escape(selection["name"])}</div>
                    <div class="rx-mute">{html.escape(selection["meta"])}</div>
                </div>''',
                unsafe_allow_html=True,
            )
            if st.button("↺ replace", key=f"{key_prefix}_replace"):
                st.session_state[state_key] = None
                st.rerun()
        else:
            st.markdown(
                f'<div class="rx-dropzone-header"><span class="rx-dropzone-icon">{icon}</span>'
                f'<strong>{html.escape(title)}</strong></div>',
                unsafe_allow_html=True,
            )
            uploaded = st.file_uploader(
                "Drop a PDF or DOCX here", type=["pdf", "docx", "txt"],
                key=f"{key_prefix}_uploader", label_visibility="visible",
            )
            samples = _sample_files(directory)
            sample_choice = st.selectbox("or pick a sample", ["— pick a sample —"] + samples, key=f"{key_prefix}_sample")

            if uploaded is not None:
                path = _save_upload(uploaded, UPLOAD_DIR)
                try:
                    char_count = len(extract_text(path))
                    meta = f"{char_count:,} characters"
                except Exception as e:
                    meta = f"Could not read this file: {e}"
                st.session_state[state_key] = {"path": path, "name": uploaded.name, "meta": meta}
                st.rerun()
            elif sample_choice != "— pick a sample —":
                path = str(directory / sample_choice)
                char_count = len(extract_text(path))
                st.session_state[state_key] = {"path": path, "name": sample_choice, "meta": f"{char_count:,} characters · sample file"}
                st.rerun()

    return st.session_state.get(state_key)


def _run_pipeline_with_progress(jd_sel: dict, resume_sel: dict, company: str) -> None:
    labels = [
        "Reading the job description...",
        "Reading your resume...",
        "Building your profile...",
        f"Checking against {company}...",
        "Matching to this role...",
    ]
    placeholders = [st.empty() for _ in labels]
    for ph, label in zip(placeholders, labels):
        ph.markdown(f'<div class="rx-progress-line">{html.escape(label)}</div>', unsafe_allow_html=True)

    def _done(i: int, label: str, suffix: str = "") -> None:
        placeholders[i].markdown(
            f'<div class="rx-progress-line done">{html.escape(label)} <b>✓{" " + suffix if suffix else ""}</b></div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.25)

    try:
        jd_text = extract_text(jd_sel["path"])
        _, guessed_role = guess_company_and_role(jd_text, jd_sel["name"])
        jd_payload = analyse_jd(jd_text, jd_sel["name"], company=company, role=guessed_role)
        save_json("jd_skills.json", jd_payload)
        mark("m1_jd_analytics", True, f"{len(jd_payload['skills'])} skills · {jd_sel['name']}")
        _done(0, labels[0], f"{len(jd_payload['skills'])} skills found")

        resume_text = extract_text(resume_sel["path"])
        resume_payload = parse_resume(resume_text, resume_sel["name"])
        save_json("resume_skills.json", resume_payload)
        mark("m2_resume_parsing", True, f"{len(resume_payload['skills'])} skills · {resume_payload['candidate_name']}")
        _done(1, labels[1], f"{len(resume_payload['skills'])} skills found")

        profile = build_profile({}, resume_payload)
        save_json("profile.json", profile)
        mark("m3_profile_builder", True, f"{profile['name'] or '(unnamed)'} · {len(profile['skills'])} skills")
        _done(2, labels[2])

        company_data = load_company_data()
        talent_check = run_talent_check(profile, company, company_data)
        save_json("talent_check_result.json", talent_check)
        mark("m4_talent_check", True, f"{company} · readiness {talent_check['readiness_score']}")
        _done(3, labels[3])

        skill_match = match_skills(profile, jd_payload)
        save_json("skill_match_result.json", skill_match)
        mark("m5_skill_matching", True, f"match {skill_match['match_score']} · {len(skill_match['missing_skills'])} missing skills")
        _done(4, labels[4])

        time.sleep(0.3)
        # A new candidate/JD was just analysed — drop any working edits Screen 2
        # was holding for the previous run so it re-initialises from fresh data.
        for key in list(st.session_state.keys()):
            if key.startswith("s2_"):
                del st.session_state[key]
        st.session_state.step = 2
        st.rerun()
    except Exception as e:
        st.error(f"Something went wrong while analysing your fit: {e}")


def render_screen1() -> None:
    st.markdown(
        '<h1 class="rx-page-title">Intelligent Resume Screening and Candidate Shortlisting</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="rx-body rx-mute">Upload a job description and your resume. We\'ll show you exactly what\'s missing.</p>',
        unsafe_allow_html=True,
    )
    st.write("")

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        jd_sel = _dropzone("jd_selection", "📄", "Job description", JD_DIR, "jd")
    with col2:
        resume_sel = _dropzone("resume_selection", "👤", "Your resume", RESUME_DIR, "resume")

    company = None
    company_names = sorted(load_company_data().keys())
    if jd_sel and company_names:
        st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
        st.markdown("**Target company**")
        try:
            jd_text_preview = extract_text(jd_sel["path"])
            guessed_company, _ = guess_company_and_role(jd_text_preview, jd_sel["name"])
        except Exception:
            guessed_company = ""
        default_idx = company_names.index(guessed_company) if guessed_company in company_names else 0
        company = st.selectbox("Target company", company_names, index=default_idx, key="s1_company", label_visibility="collapsed")
        st.caption("Auto-detected from the job description. Change if wrong.")

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    ready = bool(jd_sel) and bool(resume_sel) and bool(company)
    clicked = st.button("Analyse my fit  →", type="primary", disabled=not ready, key="s1_analyse")

    if clicked and ready:
        _run_pipeline_with_progress(jd_sel, resume_sel, company)


# ===========================================================================
# Screen 2 · Your profile
# ===========================================================================

def _render_skill_chips(skills: list[dict]) -> None:
    if not skills:
        st.caption("No skills yet — add one below.")
        return
    by_cat: dict[str, list[dict]] = {}
    for s in skills:
        by_cat.setdefault(s["category_code"], []).append(s)

    rows = []
    for code in sorted(by_cat, key=lambda c: CATEGORY_NAMES.get(c, c)):
        chips = "".join(
            f'<span class="rx-chip rx-chip-{s["confidence"]}">{html.escape(s["skill_name"])}</span>'
            for s in by_cat[code]
        )
        rows.append(
            f'<div class="rx-chip-row"><span class="rx-chip-cat-label">{html.escape(CATEGORY_NAMES.get(code, code))}</span>{chips}</div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def _parse_platform_username(raw: str) -> str:
    raw = raw.strip().rstrip("/")
    if not raw:
        return ""
    return raw.split("/")[-1]


def _coding_profile_deltas(working_skills, hackathons, internships, certifications, coding_profiles, platform):
    """Compare estimated levels with vs without this one platform's data, for the
    'DSA raised from 6 to 8 (verified)' line in F1.3."""
    base_profile = {
        "skills": working_skills, "hackathons": hackathons,
        "internships": internships, "certifications": certifications,
    }
    without = {**coding_profiles, platform: None}
    with_it = coding_profiles

    before = estimate_candidate_levels_detailed({**base_profile, "coding_profiles": without})
    after = estimate_candidate_levels_detailed({**base_profile, "coding_profiles": with_it})

    deltas = []
    for code in ("DSA", "COD", "APTI"):
        before_level = before[code]["level"]
        after_level = after[code]["level"]
        if after_level > before_level and after[code]["source"] == "verified":
            deltas.append(f"{CATEGORY_NAMES[code]} raised from {before_level} to {after_level} (verified)")
    return deltas


def _render_coding_profiles_section(working_skills, hackathons, internships, certifications) -> None:
    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("<h3>Coding profiles (optional)</h3>", unsafe_allow_html=True)
        st.caption(
            "Verified practice data. This replaces our estimate for DSA, "
            "Coding and Aptitude with your actual numbers."
        )

        coding_profiles = st.session_state.s2_coding_profiles

        # --- LeetCode ---
        lc1, lc2 = st.columns([4, 1])
        lc_input = lc1.text_input(
            "LeetCode", key="s2_leetcode_input", placeholder="leetcode.com/u/your_username",
        )
        if lc2.button("fetch", key="s2_leetcode_fetch_btn"):
            username = _parse_platform_username(lc_input)
            result = fetch_leetcode(username)
            st.session_state.s2_leetcode_error = None
            if result["stats"]:
                coding_profiles["leetcode"] = result["stats"]
            elif result["error"]:
                st.session_state.s2_leetcode_error = result["error"]
            st.rerun()

        if st.session_state.get("s2_leetcode_error"):
            st.warning(st.session_state.s2_leetcode_error)

        lc_data = coding_profiles.get("leetcode")
        if lc_data:
            summary = f"✓ LeetCode: {lc_data.get('total_solved', 0)} solved · {lc_data.get('hard', 0)} hard"
            if lc_data.get("contest_rating"):
                summary += f" · rating {lc_data['contest_rating']}"
            st.markdown(summary)
            for d in _coding_profile_deltas(working_skills, hackathons, internships, certifications, coding_profiles, "leetcode"):
                st.caption(f"→ {d}")

        with st.expander("Enter LeetCode numbers manually instead"):
            m1, m2, m3, m4, m5 = st.columns(5)
            total = m1.number_input("Total solved", min_value=0, step=1, key="s2_lc_total")
            easy = m2.number_input("Easy", min_value=0, step=1, key="s2_lc_easy")
            medium = m3.number_input("Medium", min_value=0, step=1, key="s2_lc_medium")
            hard = m4.number_input("Hard", min_value=0, step=1, key="s2_lc_hard")
            rating = m5.number_input("Contest rating", min_value=0, step=1, key="s2_lc_rating")
            if st.button("Save LeetCode numbers", key="s2_lc_manual_save"):
                coding_profiles["leetcode"] = manual_leetcode_stats(
                    _parse_platform_username(lc_input), int(total), int(easy), int(medium),
                    int(hard), int(rating) if rating else None,
                )
                st.rerun()

        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

        # --- HackerRank ---
        hr1, hr2 = st.columns([4, 1])
        hr_input = hr1.text_input(
            "HackerRank", key="s2_hackerrank_input", placeholder="hackerrank.com/your_username",
        )
        if hr2.button("fetch", key="s2_hackerrank_fetch_btn"):
            username = _parse_platform_username(hr_input)
            result = fetch_hackerrank(username)
            st.session_state.s2_hackerrank_error = None
            if result["stats"]:
                coding_profiles["hackerrank"] = result["stats"]
            elif result["error"]:
                st.session_state.s2_hackerrank_error = result["error"]
            st.rerun()

        if st.session_state.get("s2_hackerrank_error"):
            st.warning(st.session_state.s2_hackerrank_error)

        hr_data = coding_profiles.get("hackerrank")
        if hr_data:
            st.markdown(
                f"✓ HackerRank: {hr_data.get('problem_solving_stars', 0)}★ Problem Solving · "
                f"{hr_data.get('language_stars', 0)}★ language track"
            )
            for d in _coding_profile_deltas(working_skills, hackathons, internships, certifications, coding_profiles, "hackerrank"):
                st.caption(f"→ {d}")

        with st.expander("Enter HackerRank numbers manually instead"):
            h1, h2, h3 = st.columns(3)
            ps_stars = h1.number_input("Problem Solving stars", min_value=0, max_value=5, step=1, key="s2_hr_ps_stars")
            lang_stars = h2.number_input("Language track stars", min_value=0, max_value=5, step=1, key="s2_hr_lang_stars")
            gold = h3.number_input("Gold badges", min_value=0, step=1, key="s2_hr_gold")
            if st.button("Save HackerRank numbers", key="s2_hr_manual_save"):
                coding_profiles["hackerrank"] = manual_hackerrank_stats(
                    _parse_platform_username(hr_input), int(ps_stars), int(lang_stars), int(gold),
                )
                st.rerun()


def render_screen2() -> None:
    profile = load_json("profile.json") or {}
    resume_payload = load_json("resume_skills.json") or {}

    if "s2_working_skills" not in st.session_state:
        st.session_state.s2_working_skills = list(profile.get("skills", []))
    if "s2_preferred_roles" not in st.session_state:
        st.session_state.s2_preferred_roles = list(profile.get("preferred_roles", []))
    if "s2_coding_profiles" not in st.session_state:
        st.session_state.s2_coding_profiles = dict(
            profile.get("coding_profiles") or {"leetcode": None, "hackerrank": None}
        )
    if "s2_initialized" not in st.session_state:
        st.session_state.s2_name = profile.get("name", "")
        st.session_state.s2_email = profile.get("email", "")
        st.session_state.s2_education = profile.get("education", "")
        st.session_state.s2_hackathons = "\n".join(profile.get("hackathons", []))
        st.session_state.s2_internships = "\n".join(profile.get("internships", []))
        st.session_state.s2_certifications = "\n".join(profile.get("certifications", []))
        st.session_state.s2_initialized = True

    st.markdown("<h1>We read your resume. Add what it missed.</h1>", unsafe_allow_html=True)
    st.markdown(
        '<p class="rx-body rx-mute">Resumes undersell people. Hackathons, certifications and side projects all count — add them here.</p>',
        unsafe_allow_html=True,
    )
    st.write("")

    with st.container(border=True):
        col1, col2 = st.columns([3, 2])
        with col1:
            name = st.text_input("Name", key="s2_name")
            education = st.text_input("Education", key="s2_education")
        with col2:
            email = st.text_input("Email", key="s2_email")
            if resume_payload.get("candidate_name"):
                st.caption(f"✎ pre-filled from {html.escape(resume_payload['candidate_name'])}'s resume")

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    st.markdown(f"<h3>Skills we found ({len(st.session_state.s2_working_skills)})</h3>", unsafe_allow_html=True)
    st.caption("● solid = high confidence    ○ outlined = medium    ┄ dashed = low")
    _render_skill_chips(st.session_state.s2_working_skills)

    if "s2_skill_input_key" not in st.session_state:
        st.session_state.s2_skill_input_key = 0

    with st.expander("+ add a skill"):
        c1, c2, c3 = st.columns([3, 2, 1])
        new_name = c1.text_input(
            "name", key=f"s2_new_skill_name_{st.session_state.s2_skill_input_key}",
            label_visibility="collapsed", placeholder="e.g. Docker",
        )
        new_cat = c2.selectbox("category", ALL_CODES, key="s2_new_skill_cat", label_visibility="collapsed",
                                format_func=lambda c: CATEGORY_NAMES.get(c, c))
        if c3.button("Add", key="s2_add_skill_btn") and new_name.strip():
            st.session_state.s2_working_skills.append({
                "skill_name": new_name.strip(), "category_code": new_cat,
                "evidence": "self-reported", "confidence": "high",
            })
            # Rotate the widget key instead of writing to session_state after the
            # widget was already instantiated this run — Streamlit forbids that.
            st.session_state.s2_skill_input_key += 1
            st.rerun()

    if st.session_state.s2_working_skills:
        labels = [f'{CATEGORY_NAMES.get(s["category_code"], s["category_code"])} · {s["skill_name"]}'
                  for s in st.session_state.s2_working_skills]
        with st.expander("− remove skills"):
            to_remove = st.multiselect("Select skills to remove", labels, key="s2_remove_select")
            if to_remove and st.button("Remove selected", key="s2_remove_btn"):
                st.session_state.s2_working_skills = [
                    s for s, l in zip(st.session_state.s2_working_skills, labels) if l not in to_remove
                ]
                st.rerun()

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    st.markdown("<h3>What else have you done?</h3>", unsafe_allow_html=True)
    hackathons_text = st.text_area("Hackathons (one per line)", key="s2_hackathons",
                                    placeholder="e.g. Finalist, national-level 24-hour hackathon")
    internships_text = st.text_area("Internships (one per line)", key="s2_internships",
                                     placeholder="e.g. Backend intern, product startup")
    certifications_text = st.text_area("Certifications (one per line)", key="s2_certifications",
                                        placeholder="No certifications yet — add any you're working towards.")

    _render_coding_profiles_section(
        st.session_state.s2_working_skills,
        [l.strip() for l in hackathons_text.splitlines() if l.strip()],
        [l.strip() for l in internships_text.splitlines() if l.strip()],
        [l.strip() for l in certifications_text.splitlines() if l.strip()],
    )

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    st.markdown("**Preferred roles**")
    if st.session_state.s2_preferred_roles:
        chips = "".join(f'<span class="rx-chip rx-chip-medium">{html.escape(r)}</span>' for r in st.session_state.s2_preferred_roles)
        st.markdown(f'<div class="rx-chip-row">{chips}</div>', unsafe_allow_html=True)
    if "s2_role_input_key" not in st.session_state:
        st.session_state.s2_role_input_key = 0

    rc1, rc2 = st.columns([4, 1])
    new_role = rc1.text_input(
        "role", key=f"s2_new_role_{st.session_state.s2_role_input_key}",
        label_visibility="collapsed", placeholder="e.g. Software Engineer",
    )
    if rc2.button("+ add", key="s2_add_role_btn") and new_role.strip():
        if new_role.strip() not in st.session_state.s2_preferred_roles:
            st.session_state.s2_preferred_roles.append(new_role.strip())
        st.session_state.s2_role_input_key += 1
        st.rerun()
    if st.session_state.s2_preferred_roles:
        rem = st.selectbox("remove a role", ["—"] + st.session_state.s2_preferred_roles,
                            key="s2_remove_role_select", label_visibility="collapsed")
        if rem != "—" and st.button("Remove role", key="s2_remove_role_btn"):
            st.session_state.s2_preferred_roles.remove(rem)
            st.rerun()

    st.caption("These feed into your Aptitude, Communication and Software Engineering scores.")

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("← back", key="s2_back_btn"):
            st.session_state.step = 1
            st.rerun()
    with b2:
        if st.button("See my results  →", type="primary", key="s2_continue_btn"):
            profile_new = {
                "name": name, "email": email, "education": education,
                "skills": st.session_state.s2_working_skills,
                "hackathons": [l.strip() for l in hackathons_text.splitlines() if l.strip()],
                "internships": [l.strip() for l in internships_text.splitlines() if l.strip()],
                "certifications": [l.strip() for l in certifications_text.splitlines() if l.strip()],
                "preferred_roles": st.session_state.s2_preferred_roles,
                "cv_file": profile.get("cv_file", ""),
                "coding_profiles": st.session_state.s2_coding_profiles,
            }
            try:
                validate_profile(profile_new)
                save_json("profile.json", profile_new)
                mark("m3_profile_builder", True, f"{profile_new['name'] or '(unnamed)'} · {len(profile_new['skills'])} skills")

                jd_payload = load_json("jd_skills.json")
                company = st.session_state.get("s1_company") or (load_json("talent_check_result.json") or {}).get("company")
                if company and jd_payload:
                    company_data = load_company_data()
                    talent_check = run_talent_check(profile_new, company, company_data)
                    save_json("talent_check_result.json", talent_check)
                    mark("m4_talent_check", True, f"{company} · readiness {talent_check['readiness_score']}")

                    skill_match = match_skills(profile_new, jd_payload)
                    save_json("skill_match_result.json", skill_match)
                    mark("m5_skill_matching", True,
                         f"match {skill_match['match_score']} · {len(skill_match['missing_skills'])} missing skills")

                st.session_state.step = 3
                st.rerun()
            except Exception as e:
                st.error(f"Could not save your profile: {e}")


# ===========================================================================
# Screen 3 · Your results
# ===========================================================================

def _generate_divergence_note(company: str, talent_check: dict, skill_match: dict) -> str:
    readiness = talent_check["readiness_score"]
    match = skill_match["match_score"]
    diff = abs(readiness - match)

    gaps_sorted = sorted((g for g in talent_check["skillset_gap"] if g["gap"]), key=lambda g: -g["gap_size"])
    jd_tested = set(skill_match.get("category_coverage", {}).keys())
    divergent = [g["category_code"] for g in gaps_sorted if g["category_code"] not in jd_tested][:3]

    if diff < 15:
        return (
            f"Your fit for this specific role tracks closely with your overall readiness for {company}. "
            f"There's no category where the company's general bar and this posting diverge much — "
            f"whatever you improve next will help both scores."
        )

    if divergent:
        names = [CATEGORY_NAMES.get(c, c) for c in divergent]
        names_text = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        stronger = "stronger" if match > readiness else "weaker"
        pronoun = "it" if len(names) == 1 else "them"
        return (
            f"{company}'s overall bar includes {names_text}. This particular role doesn't test {pronoun}. "
            f"You're a {stronger} fit for this specific job than for the company in general."
        )

    direction = "this specific role" if match > readiness else f"{company} overall"
    return (
        f"Your two scores differ mainly because of overall breadth across categories, not one specific "
        f"missing skillset — right now you're a better match for {direction}."
    )


def _ai_enabled() -> bool:
    """Sidebar toggle AND a configured key both have to be true. Off (either
    way) → every AI feature below silently uses its deterministic fallback."""
    return st.session_state.get("ai_features_toggle", True) and llm.is_enabled()


_VERDICT_SYSTEM_PROMPT = (
    "You are a placement advisor for engineering students in India. "
    "Write exactly two sentences explaining why this candidate's company-readiness "
    "score and role-fit score differ (or don't). Use only the category names and "
    "numbers in the JSON provided — never invent a score, a requirement, or a fact "
    "about the company. Name the actual categories involved. Direct and warm, no "
    "hedging, no flattery, plain language, no category codes."
)


def _ai_verdict_paragraph(profile: dict, talent_check: dict, skill_match: dict) -> str | None:
    """A2 — replaces the templated divergence note with two personalised
    sentences grounded in this candidate's own JSON. Cheapest call in the
    system; sits at the top of the screen everyone reads first."""
    user = json.dumps({
        "candidate_name": profile.get("name", ""),
        "talent_check": {
            "company": talent_check.get("company"),
            "readiness_score": talent_check.get("readiness_score"),
            "verdict": talent_check.get("verdict"),
            "skillset_gap": talent_check.get("skillset_gap"),
        },
        "skill_match": {
            "role": skill_match.get("role"),
            "match_score": skill_match.get("match_score"),
            "missing_skills": skill_match.get("missing_skills"),
            "category_coverage": skill_match.get("category_coverage"),
        },
    })
    return llm.ask(_VERDICT_SYSTEM_PROMPT, user, max_tokens=200)


def _eligibility_verdict(readiness: int, match: int) -> tuple[str, str]:
    """Plain-language eligibility summary combining both scores. Returns (headline, detail)."""
    if readiness >= 70 and match >= 70:
        return (
            "Yes — you're a strong candidate for this role.",
            "Both your readiness for the company overall and your fit for this specific posting are "
            "solid. Apply with confidence — the plan below just tightens a few remaining gaps.",
        )
    if readiness < 50 and match < 50:
        return (
            "Not yet — but you now know exactly what's missing.",
            "Both scores show real gaps. That's not a rejection, it's a checklist: work through the "
            "short, specific plan below before you apply.",
        )
    if match >= readiness + 15:
        return (
            "Maybe — you fit this specific role better than the company in general.",
            "This posting doesn't test everything the company's overall bar does. You can realistically "
            "apply to this role while you keep building toward the company's full bar.",
        )
    if readiness >= match + 15:
        return (
            "Maybe — you clear the company's general bar better than this specific role.",
            "You're closer to being company-ready than role-ready. Focus on the role-specific gaps "
            "below before applying to this exact posting.",
        )
    return (
        "Partway there — a short, specific list stands between you and a strong application.",
        "Neither score is a clear yes or no yet. The plan below is ranked by impact — start at #1.",
    )


def _render_skillset_bars(talent_check: dict) -> None:
    """One filled bar = the candidate (--bar-cand). A vertical tick = the bar to
    clear (--bar-req). Met rows go quiet; gap rows stay full-strength with the
    gap figure coloured by size — never two overlapping bars."""
    top_gaps = set(talent_check.get("top_gaps", []))
    for g in talent_check["skillset_gap"]:
        candidate, required = g["candidate_level"], g["required_level"]
        pct_candidate = max(0, min(100, candidate / 10 * 100))
        pct_required = max(0, min(100, required / 10 * 100))
        met = not g["gap"]
        flag = ' <span class="rx-bar-flag">▲</span>' if g["category_code"] in top_gaps else ""

        if met:
            value_class, value_text = "met", f"{candidate} · {required} ✓"
        else:
            value_class = "warn" if g["gap_size"] <= 2 else "bad"
            value_text = f"{candidate} · {required} −{g['gap_size']}"

        st.markdown(
            f'''<div class="rx-bar-row">
                <div class="rx-bar-label {"met" if met else ""}">{html.escape(g["category_name"])}</div>
                <div class="rx-bar-track">
                    <div class="rx-bar-fill" style="width:{pct_candidate:.0f}%;"></div>
                    <div class="rx-bar-marker" style="left:{pct_required:.0f}%;"></div>
                </div>
                <div class="rx-bar-value rx-mono {value_class}">{value_text}{flag}</div>
            </div>''',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="rx-faint" style="text-align:right; margin-top:2px;">│ required level</div>', unsafe_allow_html=True)


def _render_plan(company: str, talent_check: dict, skill_match: dict) -> None:
    st.markdown("<h3>Your plan</h3>", unsafe_allow_html=True)
    st.markdown(
        '<p class="rx-mute">Ranked by impact — fixing #1 in each list moves your score the most.</p>',
        unsafe_allow_html=True,
    )

    st.markdown(f'<p class="rx-body" style="font-weight:700;">To close the gap for {html.escape(company)}</p>', unsafe_allow_html=True)
    gap_lookup = {g["category_code"]: g for g in talent_check["skillset_gap"]}
    top_gaps = [c for c in talent_check.get("top_gaps", []) if gap_lookup.get(c, {}).get("gap")]
    if top_gaps:
        for i, code in enumerate(top_gaps, start=1):
            g = gap_lookup[code]
            if i == 1:
                note = (f"{g['gap_size']} levels below {html.escape(company)}'s bar — your single "
                        f"biggest blocker here, and the highest-impact thing to work on first")
            else:
                note = f"{g['gap_size']} levels below the bar — still worth closing before you apply"
            st.markdown(
                f'<div class="rx-body">{i}&nbsp;&nbsp;<b>{html.escape(g["category_name"])}</b>'
                f'<br><span class="rx-mute">{note}</span></div><div style="height:8px;"></div>',
                unsafe_allow_html=True,
            )
    else:
        st.success(f"No significant gaps against {company}'s bar.")

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    st.markdown('<p class="rx-body" style="font-weight:700;">To land this specific role</p>', unsafe_allow_html=True)
    missing = skill_match.get("missing_skills", [])[:5]
    if missing:
        for i, s in enumerate(missing, start=1):
            note = (f"the job description explicitly asks for this ({s['confidence']} confidence) "
                     f"and it isn't in your profile yet — the fastest way to raise your match score")
            st.markdown(
                f'<div class="rx-body">{i}&nbsp;&nbsp;<b>{html.escape(s["skill_name"])}</b>'
                f'<br><span class="rx-mute">{note}</span></div><div style="height:8px;"></div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("No missing skills for this specific role.")


def _render_gap_views(talent_check: dict) -> None:
    st.markdown("<h3>Where to focus</h3>", unsafe_allow_html=True)
    views = compute_gap_views(talent_check["skillset_gap"])

    def _rows(rows: list[dict]) -> None:
        if not rows:
            st.success("No significant gaps — you're clear across the board.")
            return
        for i, r in enumerate(rows, start=1):
            stars = "★" * r["stars"] + "☆" * (4 - r["stars"])
            st.markdown(
                f'<div class="rx-body">{i}&nbsp;&nbsp;<b>{html.escape(r["category_name"])}</b>'
                f'&nbsp;&nbsp;<span class="rx-mute">gap {r["gap_size"]} · '
                f'+{r["impact_points"]:g} readiness · ~{r["effort_hours"]} hrs · {stars}</span></div>'
                f'<div style="height:6px;"></div>',
                unsafe_allow_html=True,
            )
        if views["already_met"]:
            names = ", ".join(CATEGORY_NAMES.get(c, c) for c in views["already_met"])
            st.caption(f"Already met: {names}")

    tab_recommended, tab_impact, tab_quick = st.tabs(["Recommended", "Biggest impact", "Quickest wins"])
    with tab_recommended:
        _rows(views["recommended"])
    with tab_impact:
        _rows(views["biggest_impact"])
    with tab_quick:
        _rows(views["quickest_wins"])


def _render_simulator(talent_check: dict) -> None:
    st.markdown("<h3>What would it take?</h3>", unsafe_allow_html=True)
    st.caption("Drag a skill to see how your readiness changes.")

    gapped = [g for g in talent_check["skillset_gap"] if g["gap"]]
    met = [g for g in talent_check["skillset_gap"] if not g["gap"]]

    if not gapped:
        st.success("You already meet the bar everywhere — nothing to simulate.")
        return

    if "s3_sim_token" not in st.session_state:
        st.session_state.s3_sim_token = 0
    token = st.session_state.s3_sim_token

    overrides = {}
    for g in gapped:
        code = g["category_code"]
        overrides[code] = st.slider(
            f'{g["category_name"]}  (needs {g["required_level"]})',
            min_value=g["candidate_level"], max_value=g["required_level"],
            value=g["candidate_level"], key=f"s3_sim_{code}_{token}",
        )

    if met:
        st.caption("Already met: " + ", ".join(g["category_name"] for g in met))

    sim = simulate(talent_check, overrides)
    arrow = "▲" if sim["delta"] > 0 else "–"
    arrow_color = "#2E7D5B" if sim["delta"] > 0 else "#6B6963"
    st.markdown(
        f'<p class="rx-body" style="font-weight:700;">Readiness&nbsp; {sim["baseline_readiness"]} '
        f'&nbsp;→&nbsp; {sim["new_readiness"]} &nbsp;'
        f'<span style="color:{arrow_color};">{arrow} {abs(sim["delta"])}</span></p>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Estimated effort: {sim['effort_hours']} hours · about {sim['weeks']:g} weeks "
        f"at {sim['weekly_hours']} hrs/week"
    )

    b1, b2 = st.columns([1, 2])
    with b1:
        if st.button("reset", key="s3_sim_reset_btn"):
            st.session_state.s3_sim_token += 1
            st.rerun()
    with b2:
        if st.button("save this as my plan", key="s3_sim_save_btn"):
            save_json("plan.json", {
                "overrides": overrides, "weekly_hours": sim["weekly_hours"],
                "baseline_readiness": sim["baseline_readiness"], "new_readiness": sim["new_readiness"],
                "effort_hours": sim["effort_hours"], "weeks": sim["weeks"],
            })
            st.success("Saved — the 12-week schedule in your downloadable report will use this plan.")


def _render_company_finder(profile: dict, talent_check: dict, company_rankings: list[dict]) -> None:
    current_company = talent_check["company"]
    st.markdown("<h3>Where else you'd fit</h3>", unsafe_allow_html=True)
    st.markdown(
        f'<p class="rx-mute">You scored {talent_check["readiness_score"]} at {html.escape(current_company)}. '
        f'Here\'s where you rank highest.</p>',
        unsafe_allow_html=True,
    )

    rows = [r for r in company_rankings if r["company"] != current_company]
    only_70 = st.checkbox("Only show companies where I'm 70+", key="s3_finder_filter")
    if only_70:
        rows = [r for r in rows if r["readiness_score"] >= 70]

    show_all = st.session_state.get("s3_finder_show_all", False)
    display_rows = rows if show_all else rows[:10]

    header = st.columns([0.5, 3, 1, 2, 2, 1.4])
    for col, label in zip(header, ["#", "Company", "Score", "Verdict", "Top gap", ""]):
        col.markdown(f"**{label}**")

    company_data = load_company_data()
    for i, r in enumerate(display_rows, start=1):
        c = st.columns([0.5, 3, 1, 2, 2, 1.4])
        c[0].write(str(i))
        c[1].write(r["company"])
        c[2].write(str(r["readiness_score"]))
        c[3].write(r["verdict"])
        c[4].write(r["top_gap"] or "—")
        if c[5].button("check", key=f"s3_finder_check_{i}"):
            new_tc = run_talent_check(profile, r["company"], company_data)
            save_json("talent_check_result.json", new_tc)
            mark("m4_talent_check", True, f"{r['company']} · readiness {new_tc['readiness_score']}")
            st.session_state.s1_company = r["company"]
            st.rerun()

    st.divider()
    st.markdown(
        f'<div class="rx-body">Your target: <b>{html.escape(current_company)}</b> &nbsp; '
        f'{talent_check["readiness_score"]} &nbsp; {html.escape(talent_check["verdict"])}</div>',
        unsafe_allow_html=True,
    )

    if not show_all and len(rows) > 10:
        if st.button(f"show all {len(rows)}", key="s3_finder_show_all_btn"):
            st.session_state.s3_finder_show_all = True
            st.rerun()


_ADVISOR_SYSTEM_PROMPT = """\
You are a placement advisor for engineering students in India.
You have this candidate's complete assessment data below.

RULES
- Use only numbers present in the data. Never invent a score,
  a requirement, or a fact about a company.
- If the data can't answer something, say so plainly.
- Direct and warm. No flattery, no hedging.
- Under 150 words unless asked to elaborate.
- Never imply the candidate isn't capable — only that specific
  evidence is missing.
- Never show category codes (e.g. "DSA") — use the plain category name.

CANDIDATE PROFILE: {profile_json}
TALENT CHECK:      {talent_check_json}
SKILL MATCH:       {skill_match_json}
COMPANY BAR:       {company_bar_json}
"""

_ADVISOR_CHIPS = [
    ("What should I learn first?", "learn_first"),
    ("Am I ready anywhere?", "ready_anywhere"),
    ("How do I explain my gaps in an interview?", "explain_gaps"),
]


def _advisor_template_answer(question_key: str | None, talent_check: dict,
                              company_rankings: list[dict]) -> str:
    """A1 fallback — chips still work, answered from templates over the same
    JSON. The panel never disappears just because the API is off."""
    gap_views = compute_gap_views(talent_check["skillset_gap"])

    if question_key == "learn_first":
        if not gap_views["recommended"]:
            return "You already meet the bar everywhere that matters here — nothing pressing to learn first."
        top = gap_views["recommended"][0]
        return (
            f"Start with {top['category_name']}. It's the best return on your time: about "
            f"{top['effort_hours']} hours to close a {top['gap_size']}-level gap, recovering "
            f"roughly {top['impact_points']:g} readiness points."
        )

    if question_key == "ready_anywhere":
        if not company_rankings:
            return "No company comparison is available yet."
        best = company_rankings[0]
        if best["readiness_score"] >= 70:
            return f"Yes — you're at {best['readiness_score']} ({best['verdict']}) at {best['company']}. That's a strong match right now."
        return (
            f"Not at a strong-match level anywhere in this dataset yet. Your best fit today is "
            f"{best['company']} at {best['readiness_score']} ({best['verdict']})."
        )

    if question_key == "explain_gaps":
        gaps = sorted((g for g in talent_check["skillset_gap"] if g["gap"]), key=lambda g: -g["gap_size"])[:3]
        if not gaps:
            return "You don't have significant gaps to explain here — lead with your strengths instead."
        names = ", ".join(g["category_name"] for g in gaps)
        return (
            f"Name them directly: say you're still building {names}, and point to what you're doing "
            f"about it — your plan already has concrete next steps for each. Interviewers respond "
            f"better to a clear plan than a dodge."
        )

    if not gap_views["recommended"]:
        return "I can't reach the AI advisor right now, but your data shows no significant gaps — you're in good shape."
    top = gap_views["recommended"][0]
    return (
        f"I can't reach the AI advisor right now, so here's what your data shows directly: your "
        f"highest-priority gap is {top['category_name']} (~{top['effort_hours']} hrs to close). "
        f"Try one of the questions above for a more specific answer."
    )


def _render_advisor_chat(profile: dict, talent_check: dict, skill_match: dict,
                          company_rankings: list[dict]) -> None:
    st.markdown("<h3>Ask about your results</h3>", unsafe_allow_html=True)

    if "s3_chat_history" not in st.session_state:
        st.session_state.s3_chat_history = []

    for msg in st.session_state.s3_chat_history[-6:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    def _answer(question: str, question_key: str | None) -> None:
        st.session_state.s3_chat_history.append({"role": "user", "content": question})
        response = None
        if _ai_enabled():
            top_company_bar = load_company_data().get(talent_check["company"], {}).get("skillsets", {})
            system = _ADVISOR_SYSTEM_PROMPT.format(
                profile_json=json.dumps(profile), talent_check_json=json.dumps(talent_check),
                skill_match_json=json.dumps(skill_match), company_bar_json=json.dumps(top_company_bar),
            )
            response = llm.ask(system, question)
        if not response:
            response = _advisor_template_answer(question_key, talent_check, company_rankings)
        st.session_state.s3_chat_history.append({"role": "assistant", "content": response})
        st.session_state.s3_chat_history = st.session_state.s3_chat_history[-6:]

    chip_cols = st.columns(len(_ADVISOR_CHIPS))
    for col, (label, key) in zip(chip_cols, _ADVISOR_CHIPS):
        if col.button(label, key=f"s3_chip_{key}"):
            _answer(label, key)
            st.rerun()

    typed = st.chat_input("Type your question...")
    if typed:
        _answer(typed, None)
        st.rerun()


def render_screen3() -> None:
    profile = load_json("profile.json")
    talent_check = load_json("talent_check_result.json")
    skill_match = load_json("skill_match_result.json")
    jd_payload = load_json("jd_skills.json")

    if not (profile and talent_check and skill_match):
        st.warning("Results aren't ready yet — finish your profile first.")
        if st.button("← back to profile"):
            st.session_state.step = 2
            st.rerun()
        return

    role = jd_payload.get("role", "") if jd_payload else ""
    header_bits = [b for b in [profile.get("name"), talent_check["company"], role] if b]
    st.markdown(f'<p class="rx-body">{" · ".join(html.escape(b) for b in header_bits)}</p>', unsafe_allow_html=True)
    st.write("")

    readiness = talent_check["readiness_score"]
    match = skill_match["match_score"]

    verdict_headline, verdict_detail = _eligibility_verdict(readiness, match)
    verdict_color = _band_color(round((readiness + match) / 2))
    st.markdown(
        f'''<div class="rx-card" style="border-left: 4px solid {verdict_color};">
            <div class="rx-eyebrow">Are you eligible for this role?</div>
            <p class="rx-body" style="font-weight:700; margin: 4px 0;">{html.escape(verdict_headline)}</p>
            <p class="rx-body rx-mute" style="margin:0;">{html.escape(verdict_detail)}</p>
        </div>''',
        unsafe_allow_html=True,
    )
    readiness_color = _band_color(readiness)
    match_color = _band_color(match)
    skillsets_met = sum(1 for g in talent_check["skillset_gap"] if not g["gap"])
    skillsets_total = len(talent_check["skillset_gap"])

    st.markdown(
        f'''<div class="rx-hero-pair">
            {_hero_score_card(
                "Company readiness", readiness, readiness_color, talent_check["verdict"],
                f'vs {html.escape(talent_check["company"])}\'s bar<br>{skillsets_met} of {skillsets_total} skillsets met',
            )}
            {_hero_score_card(
                "Role fit", match, match_color, _match_band_label(match),
                f'vs this posting<br>{len(skill_match["missing_skills"])} skills missing',
            )}
        </div>''',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        ai_note = _ai_verdict_paragraph(profile, talent_check, skill_match) if _ai_enabled() else None
        note = ai_note or _generate_divergence_note(talent_check["company"], talent_check, skill_match)
        label = "✨ **Why are these different?**" if ai_note else "ℹ️ **Why are these different?**"
        st.markdown(label)
        st.markdown(f'<p class="rx-body">{html.escape(note)}</p>', unsafe_allow_html=True)

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    st.markdown("<h3>Where you stand</h3>", unsafe_allow_html=True)
    _render_skillset_bars(talent_check)

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        _render_plan(talent_check["company"], talent_check, skill_match)

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        _render_gap_views(talent_check)

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        _render_simulator(talent_check)

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    company_rankings = rank_companies(profile, load_company_data())
    with st.container(border=True):
        _render_company_finder(profile, talent_check, company_rankings)

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    plan = load_json("plan.json")
    report_md = generate_report(profile, talent_check, skill_match, company_rankings, plan)
    st.download_button(
        "⬇ Download full report", data=report_md, file_name="radix_readiness_report.md",
        mime="text/markdown", key="s3_download_report",
    )

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        _render_advisor_chat(profile, talent_check, skill_match, company_rankings)

    st.markdown('<div class="rx-section-gap"></div>', unsafe_allow_html=True)
    b1, b2, b3 = st.columns([1, 2, 1])
    with b1:
        if st.button("← edit profile", key="s3_back_btn"):
            st.session_state.step = 2
            st.rerun()
    with b2:
        company_names = sorted(load_company_data().keys())
        current_company = talent_check["company"]
        new_company = st.selectbox(
            "Try another company", company_names,
            index=company_names.index(current_company) if current_company in company_names else 0,
            key="s3_try_company", label_visibility="collapsed",
        )
    with b3:
        if new_company != current_company and st.button("Re-run", key="s3_rerun_btn"):
            fresh_profile = load_json("profile.json")
            new_tc = run_talent_check(fresh_profile, new_company, load_company_data())
            save_json("talent_check_result.json", new_tc)
            mark("m4_talent_check", True, f"{new_company} · readiness {new_tc['readiness_score']}")
            st.session_state.s1_company = new_company
            st.rerun()


# ===========================================================================
# Developer view — the original 6-tab module inspector (spec §1, §4.7)
# ===========================================================================

def _dev_skills_dataframe(skills: list[dict]) -> pd.DataFrame:
    if not skills:
        return pd.DataFrame(columns=["Category", "Skill", "Confidence", "Evidence"])
    rows = sorted(skills, key=lambda s: (s["category_code"], s["skill_name"]))
    return pd.DataFrame([
        {"Category": CATEGORY_NAMES.get(s["category_code"], s["category_code"]),
         "Skill": s["skill_name"], "Confidence": s["confidence"], "Evidence": s["evidence"]}
        for s in rows
    ])


def _dev_download_button(label: str, payload: dict, filename: str, key: str) -> None:
    st.download_button(label, data=json.dumps(payload, indent=2), file_name=filename, mime="application/json", key=key)


def _dev_status_bar(tab_key: str) -> None:
    status = get_status()
    st.markdown(f"**RADIX Talent Match — {summary_line()}**")
    icons = {"done": "✅", "pending": "⬜", "failed": "❌"}
    cols = st.columns(5)
    for col, (module_key, info) in zip(cols, status.items()):
        with col:
            icon = icons.get(info["state"], "⬜")
            st.markdown(f"{icon} **{info['label']}**")
            if info["state"] == "pending":
                st.caption("not run")
            else:
                st.caption(info.get("detail", "") or " ")
                if info.get("timestamp"):
                    st.caption(info["timestamp"])
            if info["state"] == "failed":
                with st.expander("error"):
                    st.code(info.get("detail", ""))
    if st.button("Reset all", key=f"dev_reset_all_{tab_key}"):
        reset_status()
        out_dir = pathlib.Path(DATA_OUT)
        for f in out_dir.glob("*.json"):
            if f.name != "status.json":
                f.unlink()
        st.rerun()
    st.divider()


def _dev_render_jd_result(result: dict, key_prefix: str) -> None:
    st.write(f"**{result.get('company', '(unknown company)')} — {result.get('role', '(unknown role)')}**")
    st.dataframe(_dev_skills_dataframe(result["skills"]), use_container_width=True, hide_index=True)
    with st.expander("Raw JSON"):
        st.json(result)
    _dev_download_button("Download jd_skills.json", result, "jd_skills.json", f"{key_prefix}_dl_jd")


def _dev_render_resume_result(result: dict, key_prefix: str) -> None:
    st.write(f"**{result.get('candidate_name', '(unknown candidate)')}**")
    st.dataframe(_dev_skills_dataframe(result["skills"]), use_container_width=True, hide_index=True)
    structured = result.get("structured", {})
    st.write("**Education:**", structured.get("education") or "—")
    st.write("**Projects:**", structured.get("projects") or [])
    st.write("**Experience:**", structured.get("experience") or [])
    st.write("**Certifications:**", structured.get("certifications") or [])
    with st.expander("Raw JSON"):
        st.json(result)
    _dev_download_button("Download resume_skills.json", result, "resume_skills.json", f"{key_prefix}_dl_resume")


def _dev_render_profile(profile: dict, key_prefix: str) -> None:
    st.write(f"**{profile.get('name', '(unnamed)')}** · {profile.get('email', '')}")
    st.dataframe(_dev_skills_dataframe(profile["skills"]), use_container_width=True, hide_index=True)
    with st.expander("Raw JSON"):
        st.json(profile)
    _dev_download_button("Download profile.json", profile, "profile.json", f"{key_prefix}_dl_profile")


def _dev_render_talent_check(result: dict, key_prefix: str) -> None:
    top_gaps = set(result.get("top_gaps", []))
    st.metric("Readiness Score", f"{result['readiness_score']} / 100", result["verdict"])

    gap_df = pd.DataFrame(result["skillset_gap"])
    chart_df = gap_df.set_index("category_code")[["required_level", "candidate_level"]]
    try:
        st.bar_chart(chart_df, horizontal=True, stack=False)
    except TypeError:
        st.bar_chart(chart_df)

    display_df = gap_df[["category_code", "category_name", "required_level", "required_band",
                          "candidate_level", "gap", "gap_size"]].copy()
    display_df["top gap"] = display_df["category_code"].apply(lambda c: "⚠️" if c in top_gaps else "")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.write("**Top gaps:**", ", ".join(CATEGORY_NAMES.get(c, c) for c in result.get("top_gaps", [])))
    with st.expander("Raw JSON"):
        st.json(result)
    _dev_download_button("Download talent_check_result.json", result, "talent_check_result.json", f"{key_prefix}_dl_tc")


def _dev_render_skill_match(result: dict, key_prefix: str) -> None:
    st.metric("Match Score", f"{result['match_score']} / 100")
    if result.get("message"):
        st.warning(result["message"])

    st.subheader("Missing skills — the gap list")
    if result["missing_skills"]:
        st.dataframe(pd.DataFrame(result["missing_skills"]), use_container_width=True, hide_index=True)
    else:
        st.success("No missing skills detected.")

    st.subheader("Matched skills")
    if result["matched_skills"]:
        st.dataframe(pd.DataFrame(result["matched_skills"]), use_container_width=True, hide_index=True)
    else:
        st.caption("No skills matched.")

    with st.expander("Category coverage"):
        st.json(result.get("category_coverage", {}))
    with st.expander("Raw JSON"):
        st.json(result)
    _dev_download_button("Download skill_match_result.json", result, "skill_match_result.json", f"{key_prefix}_dl_sm")


def render_developer_view() -> None:
    st.sidebar.checkbox(
        "Use LLM extraction (slower)", key="use_llm_extraction",
        help="Optional enhancement. Falls back silently to the keyword extractor on any failure. "
             "Never required for the demo to work.",
    )

    tab_names = ["JD Analytics", "Resume Parsing", "Profile Builder", "Talent Check", "Skill Matching", "Full Pipeline"]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        _dev_status_bar("jd")
        st.header("JD Analytics")
        uploaded = st.file_uploader("Upload a JD (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt", "md"], key="dev_jd_upload")
        if uploaded is not None:
            try:
                path = _save_upload(uploaded, UPLOAD_DIR)
                text = extract_text(path)
            except Exception as e:
                text = ""
                st.error(f"Could not read file: {e}")
            if text:
                guessed_company, guessed_role = guess_company_and_role(text, uploaded.name)
                company = st.text_input("Company (editable)", value=guessed_company, key="dev_jd_company_input")
                role = st.text_input("Role (editable)", value=guessed_role, key="dev_jd_role_input")
                if st.button("Analyse JD", key="dev_analyse_jd_btn"):
                    try:
                        result = analyse_jd(text, uploaded.name, company=company, role=role,
                                            use_llm=st.session_state.get("use_llm_extraction", False))
                        save_json("jd_skills.json", result)
                        mark("m1_jd_analytics", True, f"{len(result['skills'])} skills · {uploaded.name}")
                        st.rerun()
                    except Exception as e:
                        mark("m1_jd_analytics", False, str(e))
                        st.error(f"JD analysis failed: {e}")
        jd_result = load_json("jd_skills.json")
        if jd_result:
            _dev_render_jd_result(jd_result, "jd_tab")
        else:
            st.info("Upload a JD and click **Analyse JD** to see extracted skills here.")

    with tabs[1]:
        _dev_status_bar("resume")
        st.header("Resume Parsing")
        uploaded = st.file_uploader("Upload a resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt", "md"], key="dev_resume_upload")
        if uploaded is not None:
            try:
                path = _save_upload(uploaded, UPLOAD_DIR)
                text = extract_text(path)
            except Exception as e:
                text = ""
                st.error(f"Could not read file: {e}")
            if text and st.button("Parse Resume", key="dev_parse_resume_btn"):
                try:
                    result = parse_resume(text, uploaded.name, use_llm=st.session_state.get("use_llm_extraction", False))
                    save_json("resume_skills.json", result)
                    mark("m2_resume_parsing", True, f"{len(result['skills'])} skills · {result['candidate_name']}")
                    st.rerun()
                except Exception as e:
                    mark("m2_resume_parsing", False, str(e))
                    st.error(f"Resume parsing failed: {e}")
        resume_result = load_json("resume_skills.json")
        if resume_result:
            _dev_render_resume_result(resume_result, "resume_tab")
        else:
            st.info("Upload a resume and click **Parse Resume** to see extracted skills here.")

    with tabs[2]:
        _dev_status_bar("profile")
        st.header("Profile Builder")
        resume_payload = load_json("resume_skills.json")
        if resume_payload:
            prefill = prefill_from_resume(resume_payload)
            st.caption(f"Pre-filled from resume: {resume_payload.get('candidate_name', '(unknown)')}")
        else:
            prefill = {"name": "", "email": "", "education": "", "skills": [], "hackathons": [],
                       "internships": [], "certifications": [], "preferred_roles": [], "cv_file": ""}
            st.info("No resume parsed yet — run Resume Parsing first, or fill this form manually.")

        name = st.text_input("Name", value=prefill["name"], key="dev_profile_name")
        email = st.text_input("Email", value=prefill["email"], key="dev_profile_email")
        education = st.text_input("Education", value=prefill["education"], key="dev_profile_education")
        hackathons_text = st.text_area("Hackathons (one per line)", value="\n".join(prefill["hackathons"]), key="dev_profile_hackathons")
        internships_text = st.text_area("Internships (one per line)", value="\n".join(prefill["internships"]), key="dev_profile_internships")
        certifications_text = st.text_area("Certifications (one per line)", value="\n".join(prefill["certifications"]), key="dev_profile_certifications")
        preferred_roles_text = st.text_area("Preferred roles (one per line)", value="\n".join(prefill["preferred_roles"]), key="dev_profile_preferred_roles")
        cv_upload = st.file_uploader("CV (optional — defaults to the parsed resume file)", type=["pdf", "docx", "txt"], key="dev_profile_cv_upload")
        cv_file = _save_upload(cv_upload, UPLOAD_DIR) if cv_upload is not None else prefill["cv_file"]
        st.caption(f"CV reference: {cv_file or 'none'}")

        st.subheader("Skills detected from resume")
        st.dataframe(_dev_skills_dataframe(prefill["skills"]), use_container_width=True, hide_index=True)

        st.subheader("Add or edit skills manually")
        manual_df = st.data_editor(
            pd.DataFrame(columns=["skill_name", "category_code"]), num_rows="dynamic",
            column_config={"category_code": st.column_config.SelectboxColumn("category_code", options=ALL_CODES)},
            key="dev_profile_manual_skills_editor",
        )

        if st.button("Save Profile", key="dev_save_profile_btn"):
            manual_skills = [
                {"skill_name": row["skill_name"], "category_code": row.get("category_code") or "OTHER"}
                for _, row in manual_df.iterrows() if row.get("skill_name")
            ]
            form_data = {
                "name": name, "email": email, "education": education,
                "hackathons": [l.strip() for l in hackathons_text.splitlines() if l.strip()],
                "internships": [l.strip() for l in internships_text.splitlines() if l.strip()],
                "certifications": [l.strip() for l in certifications_text.splitlines() if l.strip()],
                "preferred_roles": [l.strip() for l in preferred_roles_text.splitlines() if l.strip()],
                "cv_file": cv_file, "manual_skills": manual_skills,
            }
            try:
                dev_profile = build_profile(form_data, resume_payload)
                save_json("profile.json", dev_profile)
                mark("m3_profile_builder", True, f"{dev_profile['name'] or '(unnamed)'} · {len(dev_profile['skills'])} skills")
                st.rerun()
            except Exception as e:
                mark("m3_profile_builder", False, str(e))
                st.error(f"Could not save profile: {e}")

        dev_profile = load_json("profile.json")
        if dev_profile:
            _dev_render_profile(dev_profile, "profile_tab")

    with tabs[3]:
        _dev_status_bar("talent_check")
        st.header("Talent Check")
        st.caption("Compares the candidate against a company's hiring bar across all 12 skillsets.")
        company_data = load_company_data()
        company_names = sorted(company_data.keys())
        default_idx = company_names.index("Microsoft Corporation") if "Microsoft Corporation" in company_names else 0
        dev_profile = load_json("profile.json")
        if not dev_profile:
            st.info("Run Profile Builder first, or upload a profile.")
        elif not company_names:
            st.error("No company data found. Run scripts/build_company_json.py first.")
        else:
            company = st.selectbox("Company", company_names, index=default_idx, key="dev_tc_company")
            if st.button("Run Talent Check", key="dev_run_tc_btn"):
                try:
                    result = run_talent_check(dev_profile, company, company_data)
                    save_json("talent_check_result.json", result)
                    mark("m4_talent_check", True, f"{company} · readiness {result['readiness_score']}")
                    st.rerun()
                except Exception as e:
                    mark("m4_talent_check", False, str(e))
                    st.error(f"Talent Check failed: {e}")
            result = load_json("talent_check_result.json")
            if result:
                _dev_render_talent_check(result, "tc_tab")

    with tabs[4]:
        _dev_status_bar("skill_match")
        st.header("Skill Matching")
        st.caption("Compares the candidate against one specific JD's extracted skill list.")
        jd_payload = load_json("jd_skills.json")
        dev_profile = load_json("profile.json")
        missing = []
        if jd_payload is None:
            missing.append("JD Analytics")
        if dev_profile is None:
            missing.append("Profile Builder")
        if missing:
            st.info(f"Run {' and '.join(missing)} first.")
        else:
            if st.button("Run Skill Matching", key="dev_run_sm_btn"):
                try:
                    result = match_skills(dev_profile, jd_payload)
                    save_json("skill_match_result.json", result)
                    mark("m5_skill_matching", True, f"match {result['match_score']} · {len(result['missing_skills'])} missing skills")
                    st.rerun()
                except Exception as e:
                    mark("m5_skill_matching", False, str(e))
                    st.error(f"Skill Matching failed: {e}")
            result = load_json("skill_match_result.json")
            if result:
                _dev_render_skill_match(result, "sm_tab")

    with tabs[5]:
        _dev_status_bar("pipeline")
        st.header("Full Pipeline")
        st.caption("Pick a JD, a resume, and a company. One button runs all five stages.")
        jd_files = _sample_files(JD_DIR)
        resume_files = _sample_files(RESUME_DIR)
        company_data = load_company_data()
        company_names = sorted(company_data.keys())
        default_idx = company_names.index("Microsoft Corporation") if "Microsoft Corporation" in company_names else 0
        col1, col2, col3 = st.columns(3)
        with col1:
            jd_choice = st.selectbox("JD", jd_files, key="dev_pipeline_jd")
        with col2:
            resume_choice = st.selectbox("Resume", resume_files, key="dev_pipeline_resume")
        with col3:
            company_choice = st.selectbox("Company", company_names, index=default_idx, key="dev_pipeline_company")
        if st.button("Run Full Pipeline", key="dev_run_pipeline_btn"):
            jd_path = str(JD_DIR / jd_choice)
            resume_path = str(RESUME_DIR / resume_choice)
            with st.spinner("Running all five stages..."):
                run_pipeline(jd_path, resume_path, company_choice)
            st.rerun()

        jd_result = load_json("jd_skills.json")
        resume_result = load_json("resume_skills.json")
        profile_result = load_json("profile.json")
        talent_check_res = load_json("talent_check_result.json")
        skill_match_res = load_json("skill_match_result.json")

        if any([jd_result, resume_result, profile_result, talent_check_res, skill_match_res]):
            st.subheader("1 · JD Analytics")
            if jd_result:
                _dev_render_jd_result(jd_result, "pipe_jd")
            else:
                st.error("JD Analytics failed or hasn't run — see status bar above.")
            st.subheader("2 · Resume Parsing")
            if resume_result:
                _dev_render_resume_result(resume_result, "pipe_resume")
            else:
                st.error("Resume Parsing failed or hasn't run — see status bar above.")
            st.subheader("3 · Profile Builder")
            if profile_result:
                _dev_render_profile(profile_result, "pipe_profile")
            else:
                st.error("Profile Builder failed or hasn't run — see status bar above.")
            st.subheader("4 · Talent Check")
            if talent_check_res:
                _dev_render_talent_check(talent_check_res, "pipe_tc")
            else:
                st.warning("Talent Check did not run — requires a saved profile.")
            st.subheader("5 · Skill Matching")
            if skill_match_res:
                _dev_render_skill_match(skill_match_res, "pipe_sm")
            else:
                st.warning("Skill Matching did not run — requires a saved profile and JD skills.")


# ===========================================================================
# Dispatch
# ===========================================================================

st.sidebar.toggle(
    "AI features", value=True, key="ai_features_toggle",
    help="Grounded in your own assessment JSON — the LLM explains, it never scores. "
         "Every AI feature has a deterministic fallback; off, or with no GROQ_API_KEY "
         "configured, the app works exactly the same end to end.",
)
dev_mode = st.sidebar.toggle("Developer view", value=False, key="dev_view_toggle")

if dev_mode:
    render_developer_view()
else:
    render_stepper()
    if st.session_state.step == 1:
        render_screen1()
    elif st.session_state.step == 2:
        render_screen2()
    else:
        render_screen3()
