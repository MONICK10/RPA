# RADIX Talent Match — Progress Tracker

Claude Code updates this file. Rules:

- A box is ticked **only** after the verification command has actually been run and its output shown.
- Never tick a box in advance. Never tick a box for something described but not executed.
- When ticking, fill in the time and a one-line result note.
- After ticking, stop and wait for "next".

Status legend: `[ ]` Not Started · `[~]` In Progress · `[x]` Done · `[!]` Blocked

---

## Section A · Official milestones (20)

These are the hackathon's own milestones. `Build step` refers to Section 10 of `RADIX_TALENT_MATCH_BUILD_SPEC.md`.

### Phase 1 — Planning (owner: All)

- [x] **M1 · Read the guide** — Guide, JD/resume pack, PRD, and build spec all read
  - _Build step:_ —  · _Est:_ pre-work · _Time done:_ 2026-07-18 · _Note:_ PRD, ARCHITECTURE, build spec, PROGRESS, CLAUDE_CODE_PROMPT all read
- [x] **M2 · Understand the roles** — Can state in one line what each of the 5 modules consumes and produces
  - _Build step:_ — · _Est:_ 15 min · _Time done:_ 2026-07-18 · _Note:_ confirmed to user before "go"
- [x] **M3 · Data contract locked** — `core/contract.py` exists with `ALL_CODES`, all validators, and `normalise_skill_name`
  - _Verify:_ `python -c "from core.contract import ALL_CODES; print(len(ALL_CODES))"` prints `13`
  - _Build step:_ 1 · _Est:_ 30 min · _Time done:_ 2026-07-18 · _Note:_ printed 13, as expected
- [ ] **M4 · Environment ready** — venv active, `requirements.txt` installed, sample JDs/resumes in `data/`, `streamlit hello` runs
  - _Verify:_ `pip list | grep -E "streamlit|pypdf|docx"` shows all three
  - _Build step:_ — · _Est:_ 15 min · _Time done:_ ___ · _Note:_ ___

### Phase 2 — Development

**Module 1 · JD Analytics**

- [x] **M5 · JD text extraction** — `extract_text()` returns non-empty text from a PDF and a DOCX JD
  - _Verify:_ print character count for one PDF JD and one DOCX JD; both > 500
  - _Build step:_ 5 · _Est:_ 30 min · _Time done:_ 2026-07-18 · _Note:_ Microsoft Data Analyst PDF=1633 chars, DOCX=1583 chars
- [x] **M6 · JD skill extraction** — `analyse_jd()` produces a valid skill list for **at least 3 of the 6 sample JDs**
  - _Verify:_ for each of 3 JDs print skill count and distinct category count; each ≥ 8 skills across ≥ 4 categories; all pass `validate_skill_list`
  - _Build step:_ 8 · _Est:_ 60 min · _Time done:_ 2026-07-18 · _Note:_ 6/6 JDs passed (need only 3): 11-27 skills, 5-10 categories each, all validated

**Module 2 · Resume Parsing**

- [x] **M7 · Resume text extraction** — `extract_text()` returns non-empty text from a PDF and a DOCX resume
  - _Verify:_ print character count for two resumes; both > 300
  - _Build step:_ 5 · _Est:_ 30 min · _Time done:_ 2026-07-18 · _Note:_ Priya Menon.pdf=953 chars, Rohan Verma.docx=1242 chars
- [x] **M8 · Resume skill extraction** — `parse_resume()` produces a valid skill list for **at least 2 of the 4 sample resumes**, plus structured sections
  - _Verify:_ for each of 2 resumes print skill count, candidate_name, and which `structured` keys are non-empty
  - _Build step:_ 10 · _Est:_ 60 min · _Time done:_ 2026-07-18 · _Note:_ 4/4 resumes passed (need only 2): 6-20 skills each, education/projects/experience/certifications populated

**Module 3 · Profile Builder**

- [x] **M9 · Profile form complete** — Streamlit form captures name, email, education, skills, hackathons, internships, certifications, preferred roles, CV upload
  - _Verify:_ screenshot or field list; every PRD FR-3 field present
  - _Build step:_ 11 + 13 · _Est:_ 60 min · _Time done:_ 2026-07-18 · _Note:_ live browser check (Playwright) — Name/Email/Education/Hackathons/Internships/Certifications/Preferred roles/CV/skills editor all FOUND and pre-filled from resume
- [x] **M10 · Profile save/load + merge** — A saved profile reloads identically, and resume skills merge in without duplicates
  - _Verify:_ save → load → `assert loaded == saved`; then merge a resume payload and confirm no duplicate normalised skill names
  - _Build step:_ 11 · _Est:_ 45 min · _Time done:_ 2026-07-18 · _Note:_ prefill works, dup skill merged to 1 copy at higher confidence (low→high), round trip identical: True

**Module 4 · Talent Check**

- [x] **M11 · Company skillset data loads** — `talent_check_company_skillsets.json` generated from the CSV and loads correctly
  - _Verify:_ `python scripts/build_company_json.py` prints ~98 companies; `load_company_data()["Microsoft Corporation"]["skillsets"]` has exactly 12 keys, all in `CATEGORY_CODES`
  - _Build step:_ 2 · _Est:_ 30 min · _Time done:_ 2026-07-18 · _Note:_ wrote 98 companies; Microsoft has exactly 12 skillset keys
- [x] **M12 · Talent Check scoring** — Produces readiness score + per-skillset gap list, and **scores differ across candidates**
  - _Verify:_ run a systems-leaning and a data-leaning profile against `Microsoft Corporation`; print both readiness scores side by side; **they must differ by ≥ 15 points**
  - _Build step:_ 6 + 7 · _Est:_ 60 min · _Time done:_ 2026-07-18 · _Note:_ 16-pt spread, verdicts differ too (Developing vs Significant gaps) · **scores: 50 vs 34**

**Module 5 · Skill Matching**

- [x] **M13 · JD skill list loads** — `match_skills()` reads a Module 1 output without error
  - _Verify:_ load `jd_skills.json`, print the skill count it received
  - _Build step:_ 9 · _Est:_ 20 min · _Time done:_ 2026-07-18 · _Note:_ Module 1 output consumed cleanly, 11 and 16 skills received across two JDs
- [x] **M14 · Skill match scoring** — Match score + matched list + missing list, and **scores differ across JDs**
  - _Verify:_ run the same profile against 2 different JDs; print both match scores and the top 3 missing skills for each; scores must differ
  - _Build step:_ 9 · _Est:_ 70 min · _Time done:_ 2026-07-18 · _Note:_ data-leaning profile vs Microsoft Data Analyst / Oracle App Support Analyst · **scores: 33 vs 17**

### Phase 3 — Integration (owner: All)

- [x] **M15 · Modules talk to each other** — All 5 run back to back through `pipeline.py` with no errors and no contract violations
  - _Verify:_ `python pipeline.py --jd ... --resume ... --company "Microsoft Corporation"`; all 5 JSON files written; every one passes its validator
  - _Build step:_ 12 · _Est:_ 20 min · _Time done:_ 2026-07-18 · _Note:_ ran for Microsoft + Oracle combos, 5/5 stages ✅ each run, ~0.8s; all 5 files exist and pass their validators. Fixed a Windows console UnicodeEncodeError on ✅/❌ emoji (stdout reconfigured to utf-8).
- [x] **M16 · One shared screen** — Full flow works inside the Streamlit app on the Full Pipeline tab
  - _Verify:_ `streamlit run app.py`, run the pipeline tab live, all 5 result panels render
  - _Build step:_ 13 · _Est:_ 40 min · _Time done:_ 2026-07-18 · _Note:_ Playwright-driven real browser run — clicked "Run Full Pipeline", all 5 sections rendered (JD table, resume sections, profile, Talent Check bar chart + score, Skill Matching gap list); status bar showed 5/5 ✅
- [x] **M17 · Two combos demoed** — At least **2 of the 6 JD/role combinations** run end to end successfully
  - _Verify:_ print company, role, readiness_score, match_score for each of 2 combos
  - _Build step:_ 12 · _Est:_ 20 min · _Time done:_ 2026-07-18 · _Note:_ also ran a 3rd (Google) combo to cover all three companies · **combo 1: Microsoft Corporation / Data Analyst / readiness 28 / match 11 · combo 2: Oracle Financial Services Software Limited / Associate Software Engineer / readiness 57 / match 22 · combo 3: Google LLC / Software Engineer / readiness 39 / match 34**
- [x] **M18 · Bugs triaged** — Known bugs and edge cases logged in Section D below with fix-if-time priority
  - _Build step:_ — · _Est:_ 10 min · _Time done:_ 2026-07-18 · _Note:_ 6 bugs logged as found, 5 fixed, 1 accepted (cosmetic, out of Module 2 scope) — see Section D

### Phase 4 — Presentation (owner: All)

- [ ] **M19 · Walkthrough ready** — 5–8 minute script covering problem, architecture, live demo, one challenge faced
  - _Build step:_ — · _Est:_ 30 min · _Time done:_ ___ · _Note:_ ___
- [ ] **M20 · Demo rehearsed** — Full live demo run once end to end without help
  - _Build step:_ — · _Est:_ 15 min · _Time done:_ ___ · _Note:_ ___

---

**Step 6 note:** two dummy profiles hand-written at `data/samples/profile_systems_leaning.json` (strong COD/DSA/OS/NETW, weak SQL/AI) and `data/samples/profile_data_leaning.json` (strong SQL/AI/APTI, weak OS/NETW). Both pass `validate_profile`. No PROGRESS milestone maps to this step (enabler only).

**Step 14 note:** `core/llm_extract.py` added (Anthropic Claude, model `claude-haiku-4-5`, structured JSON output matching the skill-object schema, API key via `.env` / `python-dotenv`). `analyse_jd()` and `parse_resume()` take an optional `use_llm` flag — on any exception (missing key, network, parse error) they silently fall back to the deterministic keyword extractor. Sidebar checkbox "Use LLM extraction (slower)" added to `app.py`, wired to the JD Analytics and Resume Parsing tabs only (Full Pipeline tab stays fully deterministic). `anthropic` + `python-dotenv` kept out of the base `requirements.txt`, added to `requirements-llm.txt` instead. Verified: with no API key configured, `analyse_jd(..., use_llm=True)` still returns the correct 11-skill keyword-extractor result — fallback confirmed. Live LLM success path not tested (no API key supplied — by design, not asked for). No PROGRESS milestone maps to this step (optional, no milestone attached).

### Progress summary — Claude Code updates this block after every tick

```
Phase 1 (M1–M4)    [x][x][x][ ]                 3/4
Phase 2 (M5–M14)   [x][x][x][x][x][x][x][x][x][x]  10/10
Phase 3 (M15–M18)  [x][x][x][x]                 4/4
Phase 4 (M19–M20)  [ ][ ]                       0/2

TOTAL: 17/20  ·  85%

Module status:  JD Analytics ✅  Resume Parsing ✅  Profile Builder ✅
                Talent Check ✅  Skill Matching ✅
```

Module status marks: ⚪ not started · 🟡 partial · ✅ both its milestones done · ❌ blocked

---

## Section B · Live tick system (build this — it is a required feature)

The checklist above is a document. This section is the **running application** showing the same thing live. Both are required.

### B.1 · `core/status.py`

```python
MODULES = {
    "m1_jd_analytics":   {"label": "JD Analytics",    "output": "jd_skills.json"},
    "m2_resume_parsing": {"label": "Resume Parsing",  "output": "resume_skills.json"},
    "m3_profile_builder":{"label": "Profile Builder", "output": "profile.json"},
    "m4_talent_check":   {"label": "Talent Check",    "output": "talent_check_result.json"},
    "m5_skill_matching": {"label": "Skill Matching",  "output": "skill_match_result.json"},
}

def mark(module_key: str, ok: bool, detail: str = "") -> None
def get_status() -> dict
def reset_status() -> None
def summary_line() -> str      # e.g. "3/5 modules complete"
```

Behaviour:

- `mark()` writes into `data/out/status.json`:
  ```json
  {
    "m4_talent_check": {
      "label": "Talent Check",
      "state": "done",
      "detail": "Microsoft Corporation · readiness 62",
      "timestamp": "2026-07-18T12:14:03",
      "output_file": "data/out/talent_check_result.json"
    }
  }
  ```
- `state` is one of `"done"`, `"failed"`, `"pending"`.
- `get_status()` returns the status for all 5 modules. A module is only `"done"` if **both** its status entry says done **and** its output file exists on disk **and** that file passes its validator. If the file was deleted, it reverts to `"pending"` automatically. The tick must reflect reality, never a stale record.
- Every module function calls `mark()` on success and on caught failure. Wrap each module call in `pipeline.py` so failures are recorded, not swallowed.

### B.2 · Status bar in `app.py`

Render at the **top of every tab**, always visible:

```
RADIX Talent Match — 3/5 modules complete

✅ JD Analytics      6 skills · google_software_engineer.pdf · 12:04
✅ Resume Parsing    14 skills · candidate_2.pdf · 12:06
✅ Profile Builder   Monick S · 18 skills · 12:09
⬜ Talent Check      not run
⬜ Skill Matching    not run
```

Implementation:
- Use `st.columns(5)`, one column per module.
- Icon: ✅ done · ⬜ pending · ❌ failed.
- Under each icon: the module label, then the `detail` string, then the time.
- On ❌, show the caught error message in an expander below the bar.
- Add a "Reset all" button that calls `reset_status()` and deletes `data/out/*.json`.
- Recompute status on every rerun. Never cache it.

### B.3 · Terminal ticks in `pipeline.py`

Print a live line as each stage finishes, so the CLI shows the same picture:

```
[1/5] JD Analytics ......... ✅  22 skills across 7 categories
[2/5] Resume Parsing ....... ✅  14 skills · Priya R
[3/5] Profile Builder ...... ✅  profile saved · 18 skills
[4/5] Talent Check ......... ✅  Microsoft Corporation · readiness 62 · Nearly ready
[5/5] Skill Matching ....... ✅  match 71 · 6 missing skills

PIPELINE COMPLETE · 5/5 · 4.1s
```

On failure the line becomes `❌` with the reason, and the pipeline **continues to the next stage** where possible rather than aborting. A downstream stage that cannot run without its input prints `⏭️ skipped — requires Profile Builder`.

---

## Section C · Final correctness gate

Do not declare done until every line is ticked with evidence.

- [x] Every `category_code` written anywhere is in `ALL_CODES` — grep confirms no free-text categories
  - _Verified 2026-07-18:_ `CATEGORY_CODES`/`ALL_CODES` defined exactly once, in `core/contract.py`; every other file reads `category_code` off already-validated skill dicts or imports the constant — no second hardcoded list found
- [x] Talent Check scores differ visibly across candidates (recorded in M12)
  - _Verified 2026-07-18:_ 50 vs 34 (16-pt spread) — see M12
- [x] Skill Match scores differ visibly across JDs (recorded in M14)
  - _Verified 2026-07-18:_ 33 vs 17 — see M14
- [x] Talent Check never reads a JD; Skill Matching never reads the company dataset — confirmed by grep
  - _Verified 2026-07-18:_ `modules/m4_talent_check.py` imports only `core.contract` + `core.skill_dictionary`; `modules/m5_skill_matching.py` imports only `difflib` + `core.contract`. Neither references the other's reference dataset.
- [x] Pipeline runs end to end for Google, Microsoft, and Oracle
  - _Verified 2026-07-18:_ all three ran 5/5 via CLI (see step 12 note); readiness/match scores differ per company
- [x] No unhandled exception on: missing file, empty PDF, malformed JSON, unknown company
  - _Verified 2026-07-18:_ missing JD file → pipeline stage ❌ with reason, stages 2-4 continue, stage 5 ⏭️ skipped, exit clean; empty text → `analyse_jd` returns a valid 0-skill payload; malformed JSON on disk → `load_json` returns `None`; unknown company → `run_talent_check` returns readiness 0 with empty gap list, no crash; JD with 0 skills → `match_skills` returns score 0 with explicit `message`, no ZeroDivisionError
- [x] App runs with the network disconnected
  - _Verified 2026-07-18:_ ran full CLI pipeline with `HTTP_PROXY`/`HTTPS_PROXY` poisoned to an unreachable address — 5/5 stages succeeded, ~0.7s. No network call is load-bearing (LLM path is opt-in, off by default, isolated behind try/except).
- [x] Deleting `data/out/*.json` and re-running reproduces identical results
  - _Verified 2026-07-18:_ deleted all 5 output files, ran twice, `diff`'d every file — all 5 byte-identical across runs
- [x] Full pipeline completes in under 30 seconds
  - _Verified 2026-07-18:_ every run measured 0.2s–0.8s, well under budget
- [x] Status bar shows 5/5 ✅ after a clean run
  - _Verified 2026-07-18:_ confirmed live in a real browser via Playwright — "RADIX Talent Match — 5/5 modules complete" with all 5 ✅ icons
- [x] `tests/test_smoke.py` — automated regression suite covering the above
  - _Verified 2026-07-18:_ `pytest tests/test_smoke.py -v` → **22/22 passed** in 1.98s. Covers: contract validators, skill dictionary, company data shape, storage round-trip, JD/resume extraction minimums, profile merge/dedup, both required differentiation checks (M12, M14), unknown-company and empty-JD edge cases, full pipeline for all 3 companies, missing-file graceful degradation, unsupported file extension

---

## Section D · Bug log (M18)

| # | Description | Where | Severity | Fix if time? | Status |
|---|---|---|---|---|---|
| 1 | Candidate name extraction picked up PDF header/watermark line ("RADIX Talent Match Hackathon – Test Data") instead of the actual name on the first line | `modules/m2_resume_parsing.py` `_first_nonempty_line` | visible | yes | fixed |
| 2 | `print()` of ✅/❌/⏭️ crashed with `UnicodeEncodeError` on Windows' default cp1252 console codec | `pipeline.py` | blocker | yes | fixed — stdout reconfigured to utf-8 |
| 3 | Role-title guessing missed titles that wrap across a PDF line break (e.g. "Associate Software \nEngineer") because the match was done against unnormalised whitespace | `core/extract_text.py` `guess_company_and_role` | visible | yes | fixed — whitespace collapsed before matching |
| 4 | Filename-fallback company/role guess destroyed the "-" delimiter before splitting on it (regex replaced "-" with a space first), producing garbled names like "Google LLC Data Scientist" for company | `core/extract_text.py` `guess_company_and_role` | visible | yes | fixed — split on the raw stem before cleaning |
| 5 | `st.bar_chart` defaulted to stacking `required_level` + `candidate_level` instead of comparing them, so bar length showed the sum, not a comparison | `app.py` `render_talent_check` | visible | yes | fixed — pass `stack=False` |
| 6 | Sample resumes use a combined "Hackathons / Internships" heading; the section splitter (keyed only on education/projects/experience/certifications, per build spec §4.3) files both under "internships" — a hackathon line shows in the pre-filled Internships box | `modules/m2_resume_parsing.py` `_split_sections` | cosmetic | no | not fixed — out of Module 2's contracted `structured` keys; user-editable before Save Profile |
| 7 | Every result panel read `st.session_state.get(...) or load_json(...)` — session_state was checked *first* and, once cached, never invalidated when a different tab (or the Full Pipeline tab) overwrote the same JSON file on disk. Result: a tab could show a stale cached score forever while the status bar (which always re-reads disk) showed the current one. User caught this live — screenshots showed the status bar and the metric card on the *same page* disagreeing (39 vs 41 readiness, 8 vs 34 match score). Also silently broke "Reset all" (files deleted but session_state result caches survived) | `app.py` — all 6 tabs | blocker | yes | fixed — dropped session_state as a read source everywhere; `load_json()` (disk) is now the sole source of truth for every result panel, matching the single-I/O-gate architecture rule |
| 8 | Even after fixing #7, the status bar could still show one click behind the panel below it: `render_status_bar()` runs at the *top* of each tab, before that tab's own button handler runs (Streamlit reruns the whole script top-to-bottom per click) — so on the click that changes the file, the status bar renders the *pre-click* state while the panel below renders *post-click* | `app.py` — all 5 non-pipeline button handlers | visible | yes | fixed — added `st.rerun()` after each successful save, forcing a second full top-to-bottom pass so the status bar and the result panel are always computed from the same disk state |
| 9 | `skill_name` was the raw dictionary keyword title-cased ("ai"→"Ai", "rag"→"Rag", "sql"→"Sql") — unreadable and looked wrong for acronyms | `core/skill_dictionary.py` `extract_skills` | visible | yes | fixed — added `DISPLAY_NAMES` override map (ai→AI, sql→SQL, etc.), falls back to `.title()` for everything else |
| 10 | Keyword matching used plain `str.count()` substring search with no word boundaries — e.g. keyword "rag" matched inside "coverage" (co-ve-**rag**-e), producing a false-positive AI skill from an unrelated benefits sentence. Same bug independently existed in `m4_talent_check.py`'s narrative-text scan (`kw in text`) | `core/skill_dictionary.py` `extract_skills`; `modules/m4_talent_check.py` `estimate_candidate_levels` | visible | yes | fixed — added `keyword_in_text()` / `count_keyword_occurrences()` using `\b` regex word boundaries, shared by both call sites; removed the now-unnecessary `"go "` trailing-space hack |
| 11 | Resume "Achievements" headings weren't a recognized section (`SECTION_KEYWORDS` only had education/projects/experience/certifications) — content under them was silently dropped in `_split_sections`, never reaching `structured.experience`, so achievement text (e.g. "solved 350+ problems... mentors juniors") never flowed into the profile at all | `modules/m2_resume_parsing.py` `SECTION_KEYWORDS` | visible | yes | fixed — "achievement" added as a trigger for the "experience" bucket. Residual limitation (not a bug): APTI/COMM can still read 0 if the achievement phrasing doesn't literally match the dictionary ("mentors" vs "mentoring") — deliberate per PRD §10's deterministic-extraction tradeoff; user chose to address via the existing "Use LLM extraction" toggle rather than expanding the dictionary |
| 12 | *(proposed, not a bug)* Category-level partial-credit matching for Skill Matching was proposed externally. Rejected: `ARCHITECTURE.md` §5 and PRD §4 explicitly scope Skill Matching to name-only comparison — category-level credit is Talent Check's job. Implementing it would blur the two-module distinction the product is built around | `modules/m5_skill_matching.py` | — | no | not implemented — user confirmed keep name-only |
| 13 | *(found in R2)* `summary["email"]` is always `""`. Probed with the extraction regex and a raw `@` count: **none of the four sample resume PDFs contains an email address at all** (`at_signs=0` for Priya, Rohan, Ananya, Karthik) — a property of the sample data, not an `_extract_email` bug. Consequence for RPA: the UiPath "email the candidate" step (R7 activity 12) has no address to send to | `modules/m2_resume_parsing.py` `_extract_email` (not at fault) · `pipeline.py` summary | visible | n/a | not a code bug — R7's exception table specifies "blank email → log it, skip the candidate mail, still move the file and still write the row" |
| 14 | *(found in R3, design decision)* The R3 test "feedback contains no category codes" is unsatisfiable as literally written: two of the 13 codes are also real, learnable skill names a JD legitimately asks for — `AI` and `SQL`. `CATEGORY_NAMES` makes it worse, since "AI-Native Engineering" and "SQL & Design" each contain their own code | `modules/m6_screening_agent.py` `feedback_markdown` | — | — | resolved, not dodged: added `CANDIDATE_FACING_NAMES` so those two categories render as "Machine learning" and "Databases and data modelling" — no code is ever used as a category label. The test then splits in two: (a) the 11 opaque codes must not appear as a standalone word *anywhere*, (b) `AI`/`SQL` must never appear as a category label, only as a JD skill name. A third test bans all 18 JSON field names outright |
| 15 | *(found in R4 verification)* `screening_log.csv` was written as UTF-8 with no BOM. PowerShell 5.1's `Get-Content`, Excel and UiPath's `Read CSV` all fall back to the ANSI codepage without one, so the em-dash in every `reason` cell displayed as `â€”` — the HR report would have shipped with mojibake in its most-read column | `core/storage.py` `append_log_row` | visible | yes | fixed — the header write uses `utf-8-sig` so the BOM is written exactly once; appends stay plain `utf-8` so it is never repeated mid-file. Verified: first three bytes are `239 187 191`, `Import-Csv` now renders the em-dash correctly, and a test asserts both the single BOM and an em-dash round trip |
| 16 | *(found in R6, environment — cost the most time of anything in Section F)* Any process on this machine that **moved or deleted a file whose bytes contradict its extension** (a 0-byte `scan.pdf`, then a PNG renamed to `.pdf`) was killed mid-operation. The symptoms pointed everywhere but the real cause: `reset_demo.ps1` printing only its banner and exiting **0** with the reset half done; `run_inbox.ps1` processing 4 of 5 files then vanishing with no error record and nothing caught by a `trap`; the same loop running perfectly inline. Three red herrings were chased and ruled out — `Move-Item` (works standalone), native-command stderr redirection (`2>$null` → `NativeCommandError`), and `$PSCmdlet.ShouldProcess()`. The giveaway was the Python rewrite: it also produced **no output at all** yet still deleted 4 of 5 files, which only fits a killed process losing block-buffered stdout — so not a PowerShell fault at all, but the security stack terminating any process touching the disguised file | `scripts/reset_demo.ps1`, `scripts/run_inbox.ps1` (deleted), `core/storage.py` | blocker | yes | fixed by removing the trigger rather than working around it: the unscreenable demo file is now a correctly-named `scanned_resume.png`, innocuous to the OS *and* more realistic. Three hardening changes kept, each earning its place: (a) all demo file I/O moved into Python through `core/storage.py` (`move_file`, `copy_file`, `clear_dir`, `delete_file`, `list_files`), with `reset_demo.ps1` reduced to a wrapper that touches no files; (b) `copy_file` overwrites in place instead of delete-then-copy, which fixed a *separate* real bug where two fast resets left the inbox half empty (a Windows pending delete removing the file just copied back); (c) `_remove_with_retry` retries a delete 5 times over ~1.5 s, because a file the bot moved a moment earlier can still be held by a scanner. Verified green over 3 full reset/run/reset cycles |
| 17 | *(found in R6)* A `.ps1` containing non-ASCII characters (em-dash, middle dot) is a **parse error** in Windows PowerShell 5.1 unless the file is saved UTF-8 *with* BOM — the editor writes without one, so `reset_demo.ps1` would not run at all. Separately, `$PSScriptRoot` is empty inside a `param()` default on 5.1, so `-Root` defaulted to nothing and `Split-Path` threw | `scripts/*.ps1` | blocker | yes | fixed — PowerShell files are ASCII-only (enforced by eye and by a one-line check), and the repo root is resolved in the body via `$MyInvocation.MyCommand.Path`. Both constraints are written into the script headers so the next person does not reintroduce them |

Severity: `blocker` (demo fails) · `visible` (evaluator will notice) · `cosmetic`.

---

## Section E · Time log

| Phase | Planned | Started | Finished | Actual |
|---|---|---|---|---|
| 1 · Planning | 1 h | | | |
| 2 · Development | 2 h | | | |
| 3 · Integration | 1–1.5 h | | | |
| 4 · Presentation | TBD | | | |

---

## Section F · RPA & agent milestones

From `RPA_AGENT_PROMPT.md`. The five modules, the scoring logic and the data contract do not
change — everything here is additive. Same tick rules as Section A: a box is ticked only after
its verify command has been run and its output shown.

Build order (user-approved): **R1 → R2 → R3 → R4 → R5 → R6 → R7**. R8/R9 are bonus.

- [x] **R1 · Storage: per-run output folder + log append** — `save_json`/`load_json` take an optional `out_dir`, `save_text(path, text)` added, `append_log_row(row)` appends to `data/out/screening_log.csv` with the header written once
  - _Verify:_ save the same payload to two different `out_dir`s — both exist, differ only by location; append 2 log rows → CSV has 1 header + 2 rows
  - _Est:_ 25 min · _Time done:_ 2026-10-28 · _Note:_ both files written to `runs/_verify/priya` and `runs/_verify/rohan`, byte-identical content, default `data/out` untouched; log printed 3 lines = 1 header + 2 rows. Paths now return repo-relative with forward slashes via a new `rel_path()` so UiPath never sees a backslash. No clock inside `storage.py` — the caller supplies `timestamp`, keeping the I/O gate deterministic. 50/50 tests still pass.
- [x] **R2 · `pipeline.py`: summary record, decision, exit code** — `out_dir` parameter, flat `results["summary"]`, one `RESULT_JSON ` line, exit 0/1, `--quiet` flag
  - _Verify:_ run on one good resume and one empty file; show both `RESULT_JSON` lines and both exit codes (`echo $LASTEXITCODE`)
  - _Est:_ 40 min · _Time done:_ 2026-10-28 · _Note:_ Priya Menon → readiness 24 / match 15 / stages_ok 5 / decision `pending` / **exit 0**; empty PDF → `"Resume Parsing: Cannot read an empty file"` / stages_ok 4 / decision `exception` / **exit 1**, no traceback. Non-quiet run printed the 5 tick lines + `PIPELINE COMPLETE 5/5` + **exactly one** `RESULT_JSON` line. Three runs into three `out_dir`s wrote 3 separate folders, no overwrite. `--summary` writes through `storage.save_json`, so rule 4 holds. Per resolution #1, `decide()` is NOT in `pipeline.py` — a clean run reports `decision: "pending"` and the agent (R3) decides. 50/50 tests pass.
- [x] **R3 · `modules/m6_screening_agent.py` — the agent (pure)** — `decide()`, `reroute()`, `feedback_markdown()`; thresholds from `config/screening.json`
  - _Verify:_ unit tests for every branch, including a tie exactly on each threshold
  - _Est:_ 50 min · _Time done:_ 2026-10-28 · _Note:_ `tests/test_agent.py` → **33/33 passed**, suite now **83/83**. All four `decide` branches plus both exact-threshold ties verified: 60/60→score 60→`shortlist`, 60/58→59→`review`, 40/40→40→`review`, 40/38→39→`reject`, 0/0→`reject` (a zero is a real score, only a *missing* score is an `exception`). Average uses floor division, so 57/34→45 — matches the worked example in the prompt exactly. `reroute` verified across all four cases: none, below min gain, gain big enough but the alternative is itself a reject, and a valid alternative (48 vs 19, gain 29). Score-tie break on role name proven order-independent. Module imports **only** `core.contract` — grep for `open(`/`print(`/`save_*`/`datetime`/`pathlib`/`random` returns nothing, so purity and determinism hold.
- [x] **R4 · `agent.py` — one command per resume** — primary JD run, reroute sweep over `--jd-folder`, `summary.json` + `feedback.md`, one log row, one `RESULT_JSON` line
  - _Verify:_ run all 4 sample resumes against the Microsoft Data Analyst JD; table of resume · readiness · match · decision · rerouted_to showing **≥ 3 different decisions**
  - _Est:_ 60 min · _Time done:_ built 2026-10-28, **ticked after R5 calibration** · _Note:_ **Final table — 4 distinct decisions, PASS:**
    ```
    thresholds: shortlist>=27  review>=20  reroute_min_gain=8  score=average

    resume                 readiness  match  score  decision   rerouted_to
    Priya Menon                   24     15     19  reroute    Application Support Analyst @ Oracle Financial Services Software Limited
    Rohan Verma                   39     15     27  shortlist  -
    Ananya Rao                    36     10     23  review     -
    Karthik Subramaniam           22     45     33  shortlist  -
    scan.pdf (empty)               0      0      0  exception  -

    distinct decisions: 4 -> ['exception', 'reroute', 'review', 'shortlist']
    ```
    This is the same set of outcomes as the target-behaviour table in `RPA_AGENT_PROMPT.md` §1 (review / shortlist / reroute / exception). Rohan lands on exactly 27, the shortlist line — the exact-threshold tie the R3 unit tests cover, live in the demo. Earlier build evidence: per-resume `runs/<slug>/primary/` + `alt_<jd>/` folders (6 pipeline runs for a reject, 31 stage files, no overwrite), `summary.json` byte-identical to the printed `RESULT_JSON` line, `feedback.md` written for reject/reroute only, one log row per resume, exit 0 on a decision and 1 on the unreadable file with **no traceback**. `tests/test_agent.py` 41 tests; suite **91/91**. Company auto-detection needed `config/jd_companies.json`: 4 of 6 JDs resolve from the text, but both Google JDs fall back to the filename stem "Google LLC", which is not the dataset key "Google LLC (Subsidiary of Alphabet Inc.)". _First run, on the uncalibrated 60/40 defaults, produced only 2 distinct decisions (all four samples `reject` at 19/27/23/33, plus the exception) — the tick was held until R5 moved the lines._
- [x] **R5 · Threshold calibration** — `scripts/calibrate.py` prints the score distribution; chosen thresholds written to `config/screening.json`
  - _Verify:_ printed distribution + final table showing the spread
  - _Est:_ 30 min · _Time done:_ 2026-10-28 · _Note:_ `python scripts/calibrate.py --apply` runs 4 resumes × 6 JDs = **24 real pipeline runs** and prints the full matrix, the distribution, and the reroute potential. Observed distribution:
    ```
    series       n   min  median   max   p33   p67
    readiness   24    22    29.5    41    24    36
    match       24     5    16.0    45    10    18
    average     24    13    24.0    33    20    27
    ```
    **Chosen: `shortlist_at 27`, `review_at 20`, `reroute_min_gain 8`, `score "average"`.**
    _Reasoning._ The average score occupies 13–33 across all 24 pairs — a 20-point band sitting entirely below the old review line of 40, which is why everything rejected. The two cutoffs are the **terciles of the observed distribution** (p33 = 20, p67 = 27), so each band is populated by construction rather than by taste, and they re-derive from data if the sample set changes. `reroute_min_gain 8` is the smallest gain that lets a rejected candidate reach their *best* alternative on this data: Priya scores 19 for Data Analyst and 27 for Oracle Application Support Analyst, a gain of 8.
    _One bug in my own first pass._ The script initially proposed `reroute_min_gain 1`, taking the minimum gain over *all* eligible alternatives. That is the wrong statistic — `reroute()` always picks the highest-scoring alternative, so the weak ones are irrelevant and a bar of 1 would have sent people to roles that only just clear the review line. Fixed to take the best alternative's gain per candidate, then the minimum across candidates → 8.
    _Honest limits, worth saying out loud in the review._ These cutoffs are calibrated to **four** sample resumes, so they describe this sample, not a hiring standard. They are deliberately far below any real-world bar because the deterministic keyword extractor under-credits a short resume (see Section D #11). The thresholds live in config precisely so they can be re-derived — `scripts/calibrate.py --apply` is the whole procedure, and it is one command.
- [x] **R6 · Demo data for the bot** — `data/inbox/`, `data/inbox_seed/`, `data/uipath/<Decision>/`, `config/`, `scripts/reset_demo.ps1`
  - _Verify:_ run reset, run agent over inbox, run reset again — inbox is restored
  - _Est:_ 30 min · _Time done:_ 2026-10-29 · _Note:_ **Verified over 3 full cycles, identical each time.** reset → inbox 5 files · run → inbox 0, `data/uipath` 5 files, 4 distinct decisions · reset → inbox 5, uipath 0, runs 0, log deleted. Seed is `data/inbox_seed/` (4 sample resumes + `scanned_resume.png`); `data/uipath/{Shortlisted,Review,Rerouted,Rejected,Exceptions}/` each keep a `.gitkeep`. Config files from R3/R4 are in place. Suite **97/97** (6 new R6 tests).
    ```
    file                       name                 readiness  match decision   moved to
    Ananya Rao.pdf             Ananya Rao                  36     10 review     Review
    Karthik Subramaniam.pdf    Karthik Subramaniam         22     45 shortlist  Shortlisted
    Priya Menon.pdf            Priya Menon                 24     15 reroute    Rerouted
    Rohan Verma.pdf            Rohan Verma                 39     15 shortlist  Shortlisted
    scanned_resume.png                                      0      0 exception  Exceptions
    ```
    _Two files added beyond the R6 list, both justified._ `scripts/run_inbox.py` loops the inbox, calls the agent and moves each file into its decision folder — i.e. the UiPath workflow, so the demo is runnable and this verify is checkable on a machine with no UiPath Studio, and the teammate has a working reference to compare against. `scripts/reset_demo.py` holds the reset logic; `reset_demo.ps1` is now a thin wrapper over it (R6 asks for that filename, and the team is on Windows). Neither writes Excel or sends mail — those stay UiPath activities 10–12.
    _The unscreenable file is a real `.png`, not a renamed one._ R6 allows "empty PDF or .png renamed"; both disguised forms turned out to be unusable here (Section D #16). A correctly-named PNG is also the more realistic artefact — HR photographs resumes — and it fails with a sentence an HR user can act on: `Unsupported file type '.png' … use PDF, DOCX, or TXT`. `run_inbox.py` therefore screens **every** file in the inbox regardless of extension, matching UiPath's unfiltered `Directory.GetFiles`, so nothing is ever silently skipped.
- [x] **R7 · `UIPATH_WORKFLOW.md`** — activity-by-activity spec, variables with types, exception table, config arguments, mermaid flowchart
  - _Verify:_ a reviewer can trace every activity to a real command or file in this repo
  - _Est:_ 45 min · _Time done:_ 2026-10-29 · _Note:_ 15 sections written for a teammate with no Python knowledge: the one command they call, 12 workflow arguments (nothing hard-coded), 12 typed variables, activities 1–12 with exact UiPath property values and VB.NET expressions, the Catch block, a 14-row exception table, a §10 traceability table, a verbatim `summary.json` field reference, the mermaid flowchart, a 9-step build order, and 10 gotchas.
    **Verified mechanically, not by eye** — a 50-check script asserts every path, symbol, CLI flag and JSON field the document cites actually exists: **50/50 passed**. It checks the 19 repo paths cited, the 5 decision folders, 10 Python symbols (`_slug`, `screen_resume`, `build_summary`, `append_log_row`, `SCREENING_LOG_COLUMNS`, `decide`, `feedback_markdown`, …), all 5 `agent.py` flags against the live `--help`, and that the field table matches a real `summary.json` **both ways** (no documented field missing from the file, no file field missing from the table). Two cited paths are correctly absent and asserted as such: `scripts/apply_review.py` (R8, stated as not built) and `data/uipath/Screening_Report.xlsx` (an output UiPath writes). The mermaid block was structurally checked too — 27 nodes defined, 23 referenced, none undefined, brackets and quotes balanced — though not rendered here.
    _Three recommendations in the spec come from bugs this build actually hit._ (1) Use **Start Process**, not **Invoke Power Shell** — PS 5.1 silently terminated mid-loop with exit 0 (Section D #16). (2) Read the **summary file**, not stdout — a file cannot be disturbed by library warnings on the console. (3) Set **Read Text File encoding to `utf-8`** — `feedback.md` is BOM-less UTF-8, and the default codepage renders the em-dash as `â€”`. The spec also warns that `top_gaps` is a JSON **array** needing `String.Join`, that `readiness`/`match` can be **null** and will throw on a bare `CInt`, that exit code **1 is a valid outcome** rather than a crash, and that a rejected candidate takes ~10 s because of the reroute sweep.
- [ ] **R8 · Human-in-the-loop (bonus)** — `HR Decision` column + `scripts/apply_review.py`
  - _Verify:_ a row marked Approve moves the file from `Review/` to `Shortlisted/`, logged
  - _Est:_ 30 min · _Time done:_ ___ · _Note:_ ___
- [ ] **R9 · Streamlit batch screening screen (bonus)** — Developer view tab reading `screening_log.csv`, display only
  - _Verify:_ tab shows counts per decision, the results table, and a link to each `feedback.md`
  - _Est:_ 30 min · _Time done:_ ___ · _Note:_ ___

### Progress summary — updated after every tick

```
Core (R1–R4)    [x][x][x][x]        4/4
Calibrate (R5)  [x]                 1/1
Demo (R6–R7)    [x][x]              2/2
Bonus (R8–R9)   [ ][ ]              0/2

TOTAL: 7/9  ·  78%   (everything in the Section 6 priority list is done)

Tests: 97/97 passing (22 smoke + 28 addendum + 47 agent)
Demo decisions: shortlist · review · reroute · exception (4 of 5 possible, on 4 resumes + 1 bad file)
Demo is one command: scripts\reset_demo.ps1 then scripts\run_inbox.py
Rules held: offline ✅  deterministic ✅  storage-only I/O ✅  no traceback to stdout ✅
            m1–m5 scoring untouched ✅  data contract untouched ✅
Rules held: offline ✅  deterministic ✅  storage-only I/O ✅  no traceback to stdout ✅
```
