# RADIX Talent Match — Product Requirements Document

**Version:** 1.0
**Status:** Approved for build
**Companion document:** `RADIX_TALENT_MATCH_BUILD_SPEC.md` (technical spec — read both)

---

## 1. Problem statement

A candidate preparing for placement has no reliable way to answer two distinct questions:

1. *"Am I good enough for this company in general?"*
2. *"Do I fit this one specific job posting?"*

Today they guess. They read a JD, feel vaguely unqualified or vaguely confident, and have no concrete list of what to fix. Existing tools return a single opaque "match percentage" with no explanation, which is worse than useless — it produces anxiety without direction.

RADIX already holds the data that solves this: a 12-skillset competency framework and researched hiring bars for real companies. That data has only ever been pointed at the company side of the platform.

**This product flips the lens: same data, same rigour, built for the candidate.**

---

## 2. Product goal

Give a candidate a **specific, actionable gap list** — not a score.

The score exists to make the gap list credible. The gap list is the product.

---

## 3. Target user

A final-year engineering student or early-career candidate preparing for campus or lateral placement. Technically literate, time-poor, and specifically interested in what to study next.

---

## 4. Core insight (the thing that must not be lost)

Two different questions require two different comparisons against two different reference datasets:

| | Talent Check | Skill Matching |
|---|---|---|
| Question | *Can I clear this company's bar?* | *Do I fit this one posting?* |
| Compared against | The company's expected level across 12 skillsets | The skills extracted from one specific JD |
| Reference data | Company skillset dataset (CSV) | Extracted JD skill list |
| Granularity | 12 fixed categories, level 1–10 | Individual named skills |
| Output | Readiness score + per-skillset gap | Match score + missing skill list |
| Answers | "Should I apply here at all?" | "Should I apply to *this* role?" |

A candidate can be **company-ready but role-mismatched** — strong enough for Microsoft overall, but wrong fit for the Data Analyst posting specifically. Surfacing that distinction is the product's reason to exist.

**If a build blurs these two into one score, the product has failed regardless of how well it runs.**

---

## 5. User journey

```
1. Upload a JD          → "here's what this job actually requires"
2. Upload a resume      → "here's what your resume actually shows"
3. Complete profile     → "here's what your resume missed: hackathons, certs, preferences"
4. Run Talent Check     → "here's how you stack up against this company's bar"
5. Run Skill Matching   → "here's exactly what's missing for this specific role"
```

Step 3 exists because a resume systematically undersells a candidate. Hackathons, certifications, and side projects carry real signal and are routinely omitted or buried. The profile is the candidate's chance to be assessed on everything they've actually done.

---

## 6. Functional requirements

### FR-1 · JD Analytics
- Accept a JD as PDF, DOCX, or TXT
- Extract required skills as structured objects, each mapped to one of the 12 skillset categories
- Attach evidence (the text that triggered the extraction) and a confidence level to every skill
- Correctly handle JDs written in natural prose, not just bullet lists
- Allow the user to correct the detected company and role

### FR-2 · Resume Parsing
- Accept a resume as PDF, DOCX, or TXT
- Extract skills in the identical format as FR-1
- Additionally extract education, projects, experience, certifications where present
- Tolerate format variation — never fail on an unexpected layout

### FR-3 · Profile Builder
- Present a form covering: name, email, education, skills, hackathons, internships, certifications, preferred roles, CV reference
- Pre-fill from resume parsing output when available
- Allow manual addition and editing of every field, including individual skills
- Save and reload a profile without loss

### FR-4 · Talent Check
- Let the user select any company in the dataset
- Estimate the candidate's level 1–10 in each of the 12 skillsets from profile evidence
- Compare against the company's required level per skillset
- Produce a readiness score 0–100, a verdict, a per-skillset gap breakdown, and the top three gaps
- Display required vs actual visually across all 12 skillsets

### FR-5 · Skill Matching
- Compare a candidate profile against one extracted JD skill list
- Match exactly where possible, fuzzily where the same skill is described differently
- Produce a match score, a matched list showing how each match was made, and a missing list
- Rank missing skills by importance to the JD, most important first

### FR-6 · Integrated pipeline
- Run all five stages in sequence from a single action
- Persist every intermediate output as JSON
- Display a completion indicator for each of the five stages

---

## 7. Non-functional requirements

| ID | Requirement | Rationale |
|---|---|---|
| NFR-1 | Runs fully offline, no network dependency | The demo cannot fail on a network call |
| NFR-2 | Deterministic — same inputs always give the same outputs | Results must be defensible when questioned |
| NFR-3 | Every stage independently runnable and demonstrable | One broken module cannot block the demo |
| NFR-4 | No unhandled exception reaches the user | A stack trace on screen ends the demo |
| NFR-5 | Full pipeline completes in under 30 seconds | Live walkthrough, not a batch job |
| NFR-6 | Any module replaceable by conforming to the JSON contract | Teammates' modules can be dropped in |

---

## 8. Explicit non-goals

Out of scope for this build. Do not spend time here:

- User accounts, authentication, multi-user support
- A hosted database — local JSON files only
- Live scraping of job boards
- Resume rewriting or improvement suggestions
- Interview preparation content
- Mobile layout
- Any React frontend — Streamlit is the deliverable UI

---

## 9. Success criteria

The build is successful when **all** of the following are demonstrably true:

1. All five modules run standalone against at least two different sample inputs each
2. The five modules are wired into one end-to-end flow that runs live
3. Talent Check produces **visibly different** readiness scores for different sample candidates against the same company
4. Skill Matching produces **visibly different** match scores for the same candidate against different JDs
5. Every missing skill in the output is a real, specific, learnable thing — not a vague category
6. The tool runs with the network disconnected
7. Deleting all generated JSON and re-running reproduces identical results

Criteria 3 and 4 are the ones that get tested by an evaluator. A constant score is an immediate fail: it proves the scoring logic isn't real.

---

## 10. Key design decisions and their justification

**Deterministic keyword extraction over LLM extraction.**
An LLM extractor is more impressive on paper and less reliable in a live demo. Keyword extraction with a curated 12-category dictionary produces defensible, reproducible results with zero external dependencies. LLM extraction ships as an optional enhancement behind a toggle, with automatic fallback — never as the critical path.

**Credit capped at the required level in the readiness score.**
A candidate at level 10 in Coding and level 0 in SQL should not score the same as a candidate at level 5 in both. Capping credit at the bar prevents one strength from masking a gap. This is a deliberate product judgement about what "ready" means, and it should be stated out loud during the demo.

**Confidence-weighted match scoring.**
A skill the JD mentions three times matters more than one mentioned in passing. Weighting matched skills by extraction confidence makes the match score reflect the posting's actual emphasis rather than treating a checklist of terms as equally important.

**Gap list ranked above the score in the UI.**
The score is a hook. The gap list is what changes the candidate's behaviour. The interface reflects that priority.

**Profile as a distinct stage rather than resume-only.**
Assessing a candidate purely on their resume assesses their resume-writing, not their capability. The profile stage exists to correct that.

---

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Modules use inconsistent category codes | Integration fails at the last minute | Single shared `contract.py`; validate on every write |
| Scoring produces a constant across candidates | Immediate evaluation failure | Verify differentiation at build step 7, before proceeding |
| Teammates don't deliver their module | Pipeline incomplete | All five built to the same contract by one person; teammate modules are a drop-in upgrade, never a dependency |
| PDF text extraction returns empty | A stage silently produces nothing | Warn loudly on empty extraction; TXT fallback available |
| Time overrun | Nothing demonstrable | Build order front-loads modules 4 and 5 using a hand-written dummy profile |
