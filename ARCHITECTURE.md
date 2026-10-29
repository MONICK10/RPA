# RADIX Talent Match — Architecture

---

## 1. The one-page picture

```
        ┌──────────────┐                  ┌──────────────┐
        │   JD file    │                  │ Resume file  │
        │ (PDF / DOCX) │                  │ (PDF / DOCX) │
        └──────┬───────┘                  └──────┬───────┘
               │                                 │
               ▼                                 ▼
     ┌───────────────────┐            ┌───────────────────┐
     │ [1] JD ANALYTICS  │            │ [2] RESUME PARSE  │
     │ text → skills     │            │ text → skills     │
     └─────────┬─────────┘            └─────────┬─────────┘
               │                                 │
       jd_skills.json                  resume_skills.json
               │                                 │
               │                                 ▼
               │                      ┌───────────────────┐
               │                      │ [3] PROFILE       │
               │                      │ prefill + manual  │
               │                      │ hackathons, certs │
               │                      └─────────┬─────────┘
               │                                 │
               │                          profile.json
               │                                 │
               │                    ┌────────────┴────────────┐
               │                    ▼                         ▼
               │         ┌───────────────────┐     ┌───────────────────┐
               └────────►│ [5] SKILL MATCH   │     │ [4] TALENT CHECK  │
                         │ profile vs 1 JD   │     │ profile vs COMPANY│
                         └─────────┬─────────┘     └─────────┬─────────┘
                                   │                         │
                                   │              company_skillsets.json
                                   │                    (from CSV)
                                   ▼                         ▼
                     skill_match_result.json    talent_check_result.json
                     "what's missing for        "can I clear this
                      THIS posting"              company's bar"
```

**Note the asymmetry — it is deliberate.** JD Analytics feeds Skill Matching. The company CSV feeds Talent Check. They never cross. Two questions, two reference datasets, two answers.

---

## 2. Layers

```
┌──────────────────────────────────────────────────────┐
│  PRESENTATION        app.py (Streamlit, 6 tabs)      │
│                      status bar · forms · charts     │
├──────────────────────────────────────────────────────┤
│  ORCHESTRATION       pipeline.py                     │
│                      runs 5 stages, records status   │
├──────────────────────────────────────────────────────┤
│  DOMAIN              modules/m1 … m5                 │
│                      pure functions, no I/O          │
├──────────────────────────────────────────────────────┤
│  CORE                contract · storage · status     │
│                      extract_text · skill_dictionary │
├──────────────────────────────────────────────────────┤
│  DATA                data/  (CSV, JSON, JDs, resumes)│
└──────────────────────────────────────────────────────┘
```

**Dependency rule: arrows point downward only.** A module never imports the UI. `core` never imports `modules`. This is what makes any single module swappable for a teammate's version.

---

## 3. The three architectural rules

### Rule 1 — Pure modules

Every module function takes plain data in and returns plain data out.

```python
def run_talent_check(profile: dict, company: str, company_data: dict) -> dict
```

No file reads. No file writes. No `print`. No Streamlit calls. This makes every module testable in isolation and replaceable in one line.

### Rule 2 — One I/O gate

`core/storage.py` is the **only** file that touches disk.

```python
save_json(name, payload) → path
load_json(name) → dict | None      # None if absent, never raises
load_company_data() → dict
```

Fixed filenames in `data/out/`. If a teammate delivers a module, they only need to write a file with the right name and the right shape — nothing else has to change.

### Rule 3 — One source of truth for the contract

`core/contract.py` holds `ALL_CODES`, `CATEGORY_NAMES`, all validators, and `normalise_skill_name`. Every module imports from it. **A second copy of the category list anywhere is a bug.** This is the single most common cause of integration failure in this kind of project.

---

## 4. Data flow with state

```
step   produces                    consumed by
────────────────────────────────────────────────────────
 1     jd_skills.json              → 5
 2     resume_skills.json          → 3
 3     profile.json                → 4, 5
 4     talent_check_result.json    → UI only
 5     skill_match_result.json     → UI only

 —     company_skillsets.json      → 4 only  (generated once from CSV)
 —     status.json                 → UI + CLI tick display
```

Every stage persists immediately. Consequences:

- Any stage can be re-run alone without re-running the ones before it
- The app can be closed and reopened without losing work
- A broken stage doesn't block the others — the ones with valid outputs still demo
- A hand-written `profile.json` unblocks stages 4 and 5 before stages 2 and 3 exist

That last point is the reason the build order puts a dummy profile at step 6.

---

## 5. Two scoring engines, side by side

### Talent Check — level comparison across 12 fixed categories

```
profile ──► estimate_candidate_levels() ──► {COD: 7, DSA: 6, SQL: 3, ...}
                                                     │
company CSV ──► {COD: 8, DSA: 8, SQL: 5, ...}       │
                        │                            │
                        └──────► per-category gap ◄──┘
                                        │
                    readiness = 100 × Σ min(candidate, required)
                                       ────────────────────────
                                            Σ required
```

Credit is capped at the required level, so exceeding the bar in Coding cannot mask a zero in SQL. That cap is a product decision, not an implementation detail.

### Skill Matching — name comparison, confidence weighted

```
jd skills ──► normalise ──► exact match?  ──yes──► matched
                                │
                                no
                                ▼
                          fuzzy ≥ 0.85?  ──yes──► matched (fuzzy)
                                │
                                no
                                ▼
                            missing skill

match = 100 × Σ weight(matched) / Σ weight(all jd skills)
weight: high=3, medium=2, low=1
```

Weighting by confidence means a requirement the JD emphasises three times counts more than one mentioned in passing.

---

## 6. Extraction strategy

```
                    ┌─────────────────────┐
   document text ──►│  keyword dictionary │──► skills   ◄── ALWAYS RUNS
                    │  (deterministic)    │
                    └─────────────────────┘
                              │
                    ┌─────────▼───────────┐
                    │  LLM extractor      │──► skills   ◄── OPTIONAL, toggled
                    │  (optional)         │
                    └─────────────────────┘
                              │
                       on ANY failure
                              │
                              └──────► falls back to keyword result
```

The deterministic path is the critical path. The LLM path is an enhancement that can be switched off without the product degrading. **No network call is ever load-bearing.**

---

## 7. Status and tick propagation

```
module succeeds/fails
        │
        ▼
   status.mark(key, ok, detail)
        │
        ▼
   data/out/status.json
        │
        ├──► app.py status bar   ✅ ⬜ ❌  (top of every tab)
        └──► pipeline.py CLI     [4/5] Talent Check ...... ✅
```

`get_status()` cross-checks the recorded state against the actual output file and its validator. A stale tick is impossible — delete the output file and the tick reverts to ⬜ on the next render.

---

## 8. Failure behaviour

| Failure | Behaviour |
|---|---|
| Input file missing | Tab shows a plain-language prompt naming the stage to run first |
| PDF extracts empty text | Loud warning, suggest the TXT fallback, status ❌ with the reason |
| Unknown company | Dropdown only offers companies present in the data — unreachable by design |
| Malformed JSON on disk | `load_json` returns `None`, stage reports pending rather than crashing |
| JD has zero extracted skills | Skill Match returns score 0 with an explicit message, no division by zero |
| One stage throws | Pipeline records ❌, skips dependents with ⏭️, continues the rest |

**No unhandled exception ever reaches the screen.** A stack trace during a live walkthrough ends the demo.

---

## 9. Why this shape

| Choice | Alternative rejected | Reason |
|---|---|---|
| One app, 5 pure modules | 5 separate programs integrated later | Integration is designed in, not bolted on under time pressure |
| JSON files between stages | In-memory objects | Stages become independently runnable and demonstrable |
| Streamlit | React + API | No build step, no CORS, no second process — the demo is a live tool, not a UI exercise |
| Keyword extraction | LLM-first | Deterministic, offline, reproducible; results are defensible when questioned |
| Local files | Supabase | Zero network dependency on demo day |
| 12 fixed categories | Free-text skills | The company dataset has exactly 12 columns; the framework only works if both sides speak the same 12 |
