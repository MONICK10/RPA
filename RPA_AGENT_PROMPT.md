# Prompt — Turn RADIX Talent Match into an Agentic RPA Resume Screener

Read every .md file in this repo first (PRD, ARCHITECTURE, BUILD_SPEC, UI spec, Feature Addendum, AI/Profiles spec, PROGRESS.md) and `pipeline.py`. Then follow this prompt.

---

## 1. Context

RADIX Talent Match already works: 5 pure modules, one JSON contract, deterministic, offline, 17/20 milestones done, 22/22 smoke tests passing.

It now becomes the "brain" of a college **Robotic Process Automation (RPA)** project:

> **Intelligent Resume Screening and Candidate Shortlisting**

Today the tool screens **one** resume against **one** JD when a human clicks a button.
The new goal: a **UiPath bot** screens a **whole folder** of resumes, and an **agent layer** decides what happens to each candidate.

Concrete target behaviour — HR drops 4 resumes for "Microsoft Data Analyst" and clicks Run:

| Resume | Readiness | Role fit | Agent decision | Bot action |
|---|---|---|---|---|
| priya.pdf | 57 | 34 | review | Moved to `Review/`, row added to HR review sheet |
| rohan.docx | 72 | 61 | shortlist | Moved to `Shortlisted/`, interview email drafted |
| arun.pdf | 28 | 11 | reroute → Google SWE (fit 48) | Moved to `Rerouted/`, HR told which role fits |
| scan.pdf | — | — | exception | Moved to `Exceptions/`, reason logged |

**Division of work:**
- **Python (this repo) = the brain.** Scoring, decisions, rerouting, feedback text. Pure, deterministic, offline.
- **UiPath = the hands.** Looping files, running Python, moving files, writing Excel, sending email, handling exceptions.

---

## 2. Hard rules (do not break)

1. **Do not change the scoring logic** in modules m1–m5 or the data contract. Only add.
2. **Offline and no API keys.** The whole screening flow must run with the network off. The LLM path stays optional and OFF for screening.
3. **Deterministic.** Same inputs → byte-identical outputs.
4. **Pure modules.** New logic goes in pure functions. **Only `core/storage.py` touches disk** — including any new summary, log, or report files.
5. **Category codes only from `core/contract.py`.**
6. **No unhandled exception ever reaches stdout as a traceback.** Every failure becomes a structured result with a reason.
7. **Keep all 22 existing tests passing.** Add new tests; never delete old ones.
8. Follow the PROGRESS.md tick rules: tick only after running the verify command and showing output; stop after each tick and wait for "next".

---

## 3. What to build

Build in this order. Each item lists a **verify** step.

### R1 · Storage: per-run output folder + log append

`pipeline.py` writes to fixed filenames in `data/out/`, so resume 2 overwrites resume 1.

- Add an optional `out_dir` parameter to `save_json` / `load_json` (default stays `data/out`, so nothing existing breaks).
- Add `save_text(path, text)` for reports.
- Add `append_log_row(row: dict)` → appends to `data/out/screening_log.csv` (header written once). This is the **audit log**.

**Verify:** save the same payload to two different `out_dir`s; both files exist and differ only by location. Append 2 log rows; CSV has 1 header + 2 rows.

### R2 · `pipeline.py`: summary record, decision, exit code

`pipeline.py` may already contain a `decide()` function, a `RESULT_JSON` line, a `--summary` flag and `sys.exit`. **Keep that behaviour, but move the file write into `storage.py`** (rule 4).

- `run_pipeline(...)` gains `out_dir: str | None = None` and passes it to every save.
- Returns `results["summary"]`, a flat dict:
  `resume_file, candidate_name, email, company, role, readiness, verdict, match, top_gaps (full names, not codes), missing_skills (top 5), decision, reason, stages_ok, error`
- CLI prints exactly one line starting with `RESULT_JSON ` followed by the summary JSON.
- Exit code `0` if all 5 stages succeed, `1` otherwise.
- Add a `--quiet` flag that suppresses the tick lines and prints only `RESULT_JSON` (easier for UiPath to parse).

**Verify:** run on one good resume and one empty file. Show both `RESULT_JSON` lines and both exit codes (`echo $LASTEXITCODE` in PowerShell).

### R3 · `modules/m6_screening_agent.py` — the agent (pure)

This is the "agentic" part. It looks at results and **chooses the next action**, instead of following one fixed path.

```python
def decide(readiness: int | None, match: int | None, thresholds: dict) -> tuple[str, str]
    # returns (decision, reason)
    # decision ∈ {"shortlist", "review", "reject", "exception"}
    # reason is one plain-English sentence, e.g.
    # "Average fit 45 — between review (40) and shortlist (60); needs a human look."

def reroute(candidate_results: list[dict], primary_role: str, min_gain: int) -> dict | None
    # given the same candidate scored against every open JD,
    # return the best alternative role if it beats the primary by >= min_gain
    # and itself reaches at least "review". Else None.

def feedback_markdown(summary: dict, talent_check: dict, skill_match: dict) -> str
    # short, kind, specific feedback for a candidate:
    # strengths first, then top 3 gaps in plain names, then missing JD skills.
    # No category codes, no JSON field names. Reuse Feature Addendum F5 tone.
```

- Thresholds live in a new `config/screening.json`:
  ```json
  { "shortlist_at": 60, "review_at": 40, "reroute_min_gain": 10, "score": "average" }
  ```
  `"score"` can be `"average"`, `"readiness"`, or `"match"`.
- Decision order: missing score → `exception`; else score ≥ shortlist → `shortlist`; ≥ review → `review`; else try `reroute`; if a reroute exists → decision `reroute` with the target role; else `reject`.

**Verify:** unit tests for every branch, including a tie exactly on each threshold.

### R4 · `agent.py` — one command per resume (what UiPath calls)

```powershell
python agent.py --resume data/inbox/arun.pdf --jd data/jds/microsoft_data_analyst.pdf `
                --jd-folder data/jds --summary data/out/runs/arun/summary.json --quiet
```

1. Run the pipeline for the primary JD into `data/out/runs/<resume_stem>/primary/`.
2. If the decision would be `reject`, run the pipeline against **every other JD** in `--jd-folder` (company auto-detected with `guess_company_and_role`; allow overrides in `config/jd_companies.json`), each into its own subfolder.
3. Call `m6_screening_agent.decide` / `reroute`.
4. Write `summary.json`, `feedback.md` (for `reject` and `reroute`) via storage.
5. Append one row to `screening_log.csv`.
6. Print one `RESULT_JSON` line. Exit `0` on a decision, `1` on exception.

The summary adds: `rerouted_to_role, rerouted_to_company, rerouted_score, feedback_file`.

**Verify:** run on all 4 sample resumes against the Microsoft Data Analyst JD. Print a table: resume · readiness · match · decision · rerouted_to. **Must show at least 3 different decisions.** If not, tune `config/screening.json` (R5) and re-run.

### R5 · Threshold calibration

Real match scores in this project are low (PROGRESS shows 11–34). Fixed cutoffs like 70 would reject everyone.

- Add `scripts/calibrate.py`: runs every sample resume × every sample JD, prints the score distribution (min, max, median of readiness, match, average).
- Suggest thresholds so the samples split into shortlist / review / reject. Write the chosen values to `config/screening.json` and record them in PROGRESS.md with the reasoning.

**Verify:** printed distribution + final table showing the spread.

### R6 · Demo data for the bot

Create:
```
data/inbox/        4 sample resumes + 1 deliberately unreadable file (empty PDF or .png renamed)
data/jds/          the existing sample JDs
config/            screening.json, jd_companies.json
```
Also `scripts/reset_demo.ps1` (PowerShell — the team uses Windows) that empties `data/out/runs/`, the log, and the UiPath output folders, and restores `data/inbox/` from a `data/inbox_seed/` copy. A demo must be repeatable in one command.

**Verify:** run reset, run agent over inbox, run reset again; inbox is restored.

### R7 · `UIPATH_WORKFLOW.md` — exact spec for the UiPath teammate

The teammate builds this in UiPath Studio. Write it so they can follow it activity by activity with no Python knowledge.

Include:
- **Variables** with types (e.g. `resumeFiles : String[]`, `dtResults : DataTable`, `summaryJson : JObject`).
- **Main sequence**, numbered, using real UiPath activity names:
  1. `Build Data Table` (columns: File, Name, Email, Readiness, Match, Decision, Reason, Rerouted To, Top Gaps)
  2. `Assign` resumeFiles = `Directory.GetFiles("data\inbox")`
  3. `For Each` file
  4. `Try Catch` around the body
  5. `Invoke Power Shell` (or `Start Process` with wait) running the `agent.py` command
  6. `Read Text File` → `Deserialize JSON` on the summary file
  7. `Switch` on `decision` → `Move File` to `Shortlisted\`, `Review\`, `Rerouted\`, `Rejected\`, `Exceptions\`
  8. `Add Data Row`
  9. Catch block: move file to `Exceptions\`, add a row with the error, **continue the loop**
  10. After loop: `Write Range` → `Screening_Report.xlsx` (one sheet per decision is a bonus)
  11. `Send Outlook Mail Message` / `Send SMTP Mail Message` → HR, attach the Excel, body lists shortlisted names
  12. For `reject` / `reroute`: optional email to candidate with `feedback.md` text as the body
- **Exception handling table:** what each failure looks like and what the bot does.
- **Config:** the folder paths and the Python path as workflow arguments, not hard-coded.
- A **mermaid flowchart** of the whole flow.

**Verify:** a reviewer can trace every activity to a real command or file in this repo.

### R8 · Human-in-the-loop (bonus, only if R1–R7 are done)

- `Screening_Report.xlsx` "Review" sheet gets an `HR Decision` column (Approve / Reject).
- `scripts/apply_review.py` reads that column and moves files from `Review/` to `Shortlisted/` or `Rejected/`, logging each move.
- In UiPath this is a second small workflow: `Read Range` → `For Each Row` → `Move File`.

### R9 · Streamlit: "Batch screening" screen (bonus)

Inside **Developer view** only, add a tab that reads `screening_log.csv` and shows: counts per decision, the results table, and a link to each candidate's `feedback.md`. No new scoring — display only.

---

## 4. Tests

Add `tests/test_agent.py`:
- `decide` — every branch + exact-threshold ties
- `reroute` — no alternative, alternative below min gain, valid alternative
- `feedback_markdown` — contains no category codes (`DSA`, `CLOUD`, …) and no JSON keys
- `agent.py` on the unreadable file → exit 1, decision `exception`, no traceback in output
- two runs on different resumes do not overwrite each other's files
- full inbox run is deterministic: run twice, diff all summaries → identical

Run `pytest -v` at the end. All old and new tests must pass.

---

## 5. PROGRESS.md

Add **Section F · RPA & agent milestones** with R1–R9 in the same format as Section A (`_Verify_`, `_Time done_`, `_Note_`), plus a progress summary block. Add any bugs found to Section D.

---

## 6. Priority for the review tomorrow

If time is short, build in this order and stop wherever time runs out:

1. **R2 + R3 + R4** — the agent works from the command line
2. **R5** — thresholds give a real spread of decisions
3. **R6** — repeatable demo data
4. **R7** — UiPath spec, so the teammate can start building

R8 and R9 are for the next review.

---

## 7. Output after each step

Show: the files changed, the verify command, its real output, and the PROGRESS.md tick. Keep explanations short. Then stop and wait for "next".
