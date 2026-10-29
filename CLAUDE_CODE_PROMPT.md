# Prompt for Claude Code (VS Code)

Paste the block below into Claude Code. Have `PRD.md`, `RADIX_TALENT_MATCH_BUILD_SPEC.md`, `PROGRESS.md`, the CSV, and your sample JDs/resumes already in the folder.

---

## THE PROMPT — copy everything below this line

```
I'm building RADIX Talent Match. Four documents in this folder define it completely:

- PRD.md — what the product is, why, and what "done" means
- ARCHITECTURE.md — layers, dependency rules, data flow, scoring engines
- RADIX_TALENT_MATCH_BUILD_SPEC.md — full technical spec, data contract, algorithms,
  and a 14-step build order in Section 10
- PROGRESS.md — the official 20 hackathon milestones (Section A) that you will tick as
  you work, plus the live tick system you must build (Section B)

Read all four fully before writing a single line of code.

HOW I WANT YOU TO WORK:

1. Follow Section 10 of the build spec in exact order. Do not skip ahead and do not
   build multiple steps at once.

2. After each step:
   a. run the "Done when" verification for that step
   b. show me the actual command output proving it passed
   c. tick the mapped milestone in PROGRESS.md Section A — change "- [ ]" to "- [x]",
      fill in the time, and write a one-line result note
   d. update the progress summary block at the end of Section A (counts, percentage,
      and the per-module status marks)
   e. then STOP and wait for me to say "next"

3. If a verification fails, fix it before moving on. Never tick a box for something you
   haven't actually run. A tick means "I executed this and saw it pass" — nothing else.

4. Never invent a category code. Import ALL_CODES from core/contract.py everywhere.
   Duplicated category lists are the number one failure mode in this project.

5. Only core/storage.py touches the filesystem. No other module reads or writes files.

6. Prefer boring and deterministic over clever and fragile. No network calls anywhere
   in the critical path. The optional LLM extractor comes last, behind a toggle, with
   automatic fallback to the keyword extractor on any failure.

7. Every module must degrade gracefully. No unhandled exception may ever reach the user.
   Missing input produces a readable message, not a stack trace.

8. Build the live tick system exactly as specified in PROGRESS.md Section B — it is a
   required product feature, not optional tooling:
     - core/status.py recording completion into data/out/status.json
     - a status bar at the top of EVERY tab in app.py showing ✅ / ⬜ / ❌ for each of
       the five modules, with detail text and timestamp
     - terminal tick lines in pipeline.py, one per stage
   A tick must reflect reality: get_status() re-checks that the output file exists and
   passes its validator. Delete the file, the tick reverts. No stale ticks.

9. I am building all five modules myself. Treat the five as one codebase with five
   internal boundaries — but keep the boundaries strict enough that any one module
   could still be swapped for someone else's version conforming to the same contract.

THE TWO THINGS THAT MATTER MOST — verify both explicitly before declaring done:

  A) Talent Check must produce visibly different readiness scores for different
     candidates against the same company. A constant score means the level estimator
     is broken and the whole project fails evaluation.

  B) Talent Check and Skill Matching must stay conceptually separate. Talent Check
     compares the candidate to a COMPANY'S BAR using the CSV dataset. Skill Matching
     compares the candidate to ONE JD'S extracted skill list. Skill Matching must never
     read the company dataset. Talent Check must never read a JD. If these get blurred,
     the product is meaningless even if the code runs.

Start now with Step 1: core/contract.py. Show me the file, run the verification, tick
the box, then stop.
```

---

## Follow-up prompts to use as you go

**After each step, if the verification passed:**
```
next
```

**If something breaks:**
```
That failed. Don't rewrite the whole module — show me the specific line that's wrong
and the minimal fix. Then re-run the verification.
```

**When you reach step 7 (Talent Check):**
```
Before ticking this box: create two dummy profiles — one systems-leaning (strong
Coding/DSA/OS/Networking, weak SQL/AI) and one data-leaning (strong SQL/AI/Aptitude,
weak Networking/OS). Run both against "Microsoft Corporation" and show me both
readiness scores side by side. They must differ by at least 15 points. If they don't,
the level estimator in Step A is wrong — fix it before continuing.
```

**When you reach step 12 (pipeline):**
```
Run the CLI end to end for all three companies:
  - Google LLC (Subsidiary of Alphabet Inc.)
  - Microsoft Corporation
  - Oracle Financial Services Software Limited
Show me the readiness_score and match_score for each. Confirm all five JSON files were
written for each run. Confirm the numbers differ across companies.
```

**Before the demo:**
```
Run the full Section 11 correctness checklist from the build spec, one item at a time.
For each, show the command you ran and the output. Then update PROGRESS.md Section C.
Turn off my network and confirm the app still runs.
```

**If you're running out of time:**
```
I have N minutes left. Given PROGRESS.md, tell me the minimum remaining work to have
something demonstrable end to end, and cut everything else. Don't ask me questions —
decide and build it.
```

---

## What NOT to say to Claude Code

- ❌ "Build the whole thing" — you'll get 14 steps of unverified code and no way to find the break
- ❌ "Make it better" / "improve this" — vague; it will refactor working code
- ❌ "Add an LLM" before step 13 — the deterministic path must work first
- ❌ "Just make it work" when something fails — you'll get a hack that breaks the contract
