# RADIX Talent Match — Feature Addendum

Add-ons to the base build. Nothing here changes the five modules or the data contract — these extend the profile, the scoring inputs, and the results screen.

Build order: **F1 → F4 → F2 → F3 → F5**. F1 feeds everything else.

---

## F1 · Coding profiles (LeetCode / HackerRank)

### F1.1 · Why this belongs in the product

Every other input is self-reported. A resume that says "solved 350+ problems" is a claim. A LeetCode profile is a **verified** fact.

That distinction matters enough to become a first-class concept:

```
CONFIDENCE TIERS
  verified      ← coding profile data, weight 4   (NEW)
  high          ← self-reported, strong evidence, weight 3
  medium        ← weight 2
  low           ← weight 1
```

Add `"verified"` to the allowed `confidence` values in `core/contract.py`. It is the only tier the candidate cannot inflate.

### F1.2 · Where it fits architecturally

It is **not** a sixth module. It is a new evidence source feeding the existing pipeline:

```
resume ──────────┐
manual entry ────┼──► [3] PROFILE BUILDER ──► profile.json ──► [4] TALENT CHECK
coding profile ──┘         (new input)          (new block)      (verified boost)
```

- **Input point:** Screen 2, the profile screen. Optional, clearly marked.
- **Storage:** a new `coding_profiles` block inside `profile.json`.
- **Effect:** overrides the estimated level for **DSA, COD and APTI only**. These are exactly the three categories a resume evidences most weakly and a coding platform evidences most strongly. It touches nothing else.

### F1.3 · UI on the profile screen

```
─ Coding profiles (optional) ────────────────────────────
  Verified practice data. This replaces our estimate for
  DSA, Coding and Aptitude with your actual numbers.

  LeetCode      [ leetcode.com/u/ananya_r        ] [ fetch ]
  HackerRank    [ paste your profile URL          ] [ fetch ]

  ✓ LeetCode: 412 solved · 88 hard · rating 1847
    → DSA raised from 6 to 8 (verified)
─────────────────────────────────────────────────────────
```

Requirements:
- Both fields optional. Empty is a valid state, never a warning.
- After a successful fetch, show what was found **and what it changed**. The line "DSA raised from 6 to 8 (verified)" is the whole point — the candidate sees their effort register.
- A `verified` chip renders differently from the others: filled, with a small ✓.

### F1.4 · Fetching, and the offline problem

Fetching needs network, which breaks the "runs offline" guarantee. Resolve it like this — do not skip this design:

1. **Manual entry is always available.** Under each field, an expander: "Enter manually instead" with number inputs for solved counts, difficulty split, and rating. This path needs no network at all.
2. **Fetch is best-effort.** Wrap in try/except with a 5-second timeout. On any failure: *"Couldn't reach LeetCode. Enter your numbers manually below."* Never a stack trace, never a blocked flow.
3. **Cache every successful fetch** to `data/cache/coding_<username>.json`. Re-runs read the cache. This makes the demo reproducible and offline-safe after one successful fetch.
4. **Pre-cache your demo candidates before presenting.** Then the demo never touches the network even with fetching enabled.

LeetCode exposes a public GraphQL endpoint at `leetcode.com/graphql` for `matchedUser` stats. HackerRank is less stable — treat manual entry as the primary path there and fetch as a bonus.

### F1.5 · Mapping platform stats to levels 1–10

```python
def leetcode_to_levels(stats: dict) -> dict[str, dict]:
    """Returns {code: {"level": int, "reason": str}} for DSA, COD, APTI."""
```

**DSA — driven by volume, adjusted for difficulty and contest performance:**

| Total solved | Base level |
|---|---|
| < 50 | 3 |
| 50–149 | 5 |
| 150–299 | 6 |
| 300–499 | 7 |
| 500+ | 8 |

Then:
- Hard problems ≥ 15% of total → **+1**
- Contest rating ≥ 1800 → **+1** · ≥ 2100 → **+2**
- Cap at 10

**COD — volume implies fluency, but caps lower than DSA:**
`min(8, 3 + total_solved // 100)`

**APTI — problem-solving under constraint:**
Contest rating ≥ 1600 → 6 · ≥ 1900 → 7 · ≥ 2200 → 8. No contests → `min(7, DSA level − 1)`.

**HackerRank:** map stars per track. 5-star Problem Solving → DSA 7. 5-star in a language track → COD 7. Gold badge → +1. Treat as a floor, not an override — HackerRank stars are easier to earn than LeetCode volume.

### F1.6 · Merge rule — read this carefully

```python
# In estimate_candidate_levels(), after the resume/profile estimate:
if verified_level > estimated_level:
    final_level = verified_level
    evidence = f"verified: {reason}"
else:
    final_level = estimated_level   # keep the higher estimate
    evidence = f"estimated (coding profile suggested {verified_level})"
```

**Verified data raises a level. It never lowers one.** A candidate with strong projects but a thin LeetCode profile shouldn't be punished for not grinding problems. State this out loud in the demo — it's a defensible product decision, and someone will ask.

Record both numbers in the output so the report can show the delta.

---

## F2 · "What if" simulator

### Placement
Bottom of the results screen, in its own card titled **"What would it take?"**

### Behaviour

```
─ What would it take? ───────────────────────────────────
  Drag a skill to see how your readiness changes.

  AI               0 ──────●──── 5    (needs 7)   ~175 hrs
  Cloud / DevOps   0 ●─────────── 0   (needs 5)
  SQL              0 ───●──────── 3   (needs 5)   ~36 hrs

  Readiness   34  →  58   ▲ 24
  Estimated effort: 211 hours  ·  about 13 weeks at 16 hrs/week

  [ reset ]   [ save this as my plan ]
─────────────────────────────────────────────────────────
```

Requirements:
- One slider per category **that currently has a gap**. Categories already met are listed compactly as "already met" — no slider, no clutter.
- Slider range: current level → required level. Cannot drag above the bar, because credit is capped anyway and letting them would teach the wrong mental model.
- Recompute readiness on every change. It's 12 integers — instant, no caching needed.
- Show the delta prominently: `34 → 58 ▲ 24`.
- Effort estimate uses the F3 hours table. Show hours and a weeks figure at a stated weekly rate.
- The simulator **never** writes to `profile.json`. It is a projection. "Save this as my plan" writes to a separate `plan.json` consumed by the report.

### Why it matters in the demo
It converts a verdict into agency. "34, significant gaps" is discouraging. "Close SQL and Cloud in about 9 weeks and you're at 58" is a decision. Say that line out loud when you demo it.

---

## F3 · Effort-ranked gaps

### Hours per level point, by category

```python
HOURS_PER_LEVEL = {
    "SQL":   12,   # fastest — bounded syntax, immediate feedback
    "CLOUD": 15,
    "APTI":  15,
    "NETW":  18,
    "OS":    18,
    "COD":   20,
    "OOD":   20,
    "SWE":   20,
    "COMM":  20,
    "DSA":   30,   # slow — needs sustained practice volume
    "SYSD":  30,
    "AI":    35,   # slowest — deep prerequisites
}
```

These are estimates, and you should say so. They exist to rank, not to promise.

### The three views — show all three, they answer different questions

```python
impact_points = (gap_size / total_required) * 100   # readiness points recovered
effort_hours  = gap_size * HOURS_PER_LEVEL[code]
roi           = impact_points / effort_hours * 100  # points per 100 hours
```

| View | Sort by | Answers |
|---|---|---|
| **Biggest impact** | `impact_points` desc | "What's holding me back most?" |
| **Quickest wins** | `effort_hours` asc | "What can I fix this month?" |
| **Recommended order** | `roi` desc | "Where does my time go furthest?" |

Render as three tabs inside one card. Default to **Recommended order**.

```
─ Where to focus ────────────────────────────────────────
  [ Recommended ] [ Biggest impact ] [ Quickest wins ]

  1  SQL              gap 5   +6.5 readiness   ~60 hrs   ★★★★
  2  Cloud / DevOps   gap 5   +6.5 readiness   ~75 hrs   ★★★☆
  3  AI               gap 7   +9.1 readiness  ~245 hrs   ★★☆☆
─────────────────────────────────────────────────────────
```

The insight to state in the demo: **AI is the biggest gap but the worst first move.** SQL recovers almost as much readiness for a quarter of the time. Ranking purely by gap size would have sent this candidate down the slowest path first.

---

## F4 · Best-fit company finder

### Placement
Its own card on the results screen: **"Where else you'd fit"**

### Behaviour

```python
def rank_companies(profile: dict, company_data: dict, top_n: int = 10) -> list[dict]:
    """Run Talent Check against every company. Return the best fits."""
```

- Loop `run_talent_check` over all ~98 companies. It's 12 integer comparisons each — the whole sweep is milliseconds.
- Return company, readiness score, verdict, and the top gap.
- Sort descending.

```
─ Where else you'd fit ──────────────────────────────────
  You scored 34 at Acko. Here's where you rank highest.

   1  Zoho Corporation             78   Nearly ready   gap: AI
   2  Freshworks                   74   Nearly ready   gap: Cloud
   3  Mindtree                     71   Nearly ready   gap: SQL
   ...
  ─────────────────────────────────────────────────────
  Your target: Acko                34   Significant gaps

  [ show all 98 ]   [ run Talent Check on ▾ ]
─────────────────────────────────────────────────────────
```

Requirements:
- Always show the user's originally targeted company at the bottom for contrast. The comparison is the point.
- Clicking any row re-runs the full Talent Check against that company in place.
- A filter: "only show companies where I'm 70+".

### Why it matters
This is where 98 rows of CSV stop being a lookup table and become the product. A candidate who scores 34 at their dream company learns they're a 78 somewhere real. That reframes the whole tool from *judgement* to *guidance* — worth saying in those words during the demo.

---

## F5 · The final report

A single downloadable document the candidate keeps. This is the deliverable that outlives the session.

### Format
Generate as **Markdown first** (fast, always works), with an optional HTML/PDF render if time permits. Do not block on PDF.

### Structure

```
════════════════════════════════════════════════════
  RADIX TALENT MATCH — READINESS REPORT
  Ananya Rao · Google LLC · Software Engineer
  Generated 20 July 2026
════════════════════════════════════════════════════

1 · SUMMARY
   Company readiness  77 / 100   Nearly ready
   Role fit           88 / 100   Strong match

   One paragraph, generated, explaining what the two
   numbers mean together and why they differ.

2 · YOUR STRENGTHS
   The categories where you meet or exceed the bar,
   with the evidence that established each one.
   Lead with strengths. A report that opens with
   failure doesn't get read to the end.

3 · YOUR GAPS
   Table: category · required · yours · gap · effort
   Ordered by recommended priority (F3 ROI).

4 · WHERE TO FOCUS FIRST
   Top 3, each with:
     - what to learn, in plain terms
     - estimated hours and weeks
     - readiness points recovered
     - one concrete first step

5 · FOR THIS SPECIFIC ROLE
   The Skill Match gap list. Skills the posting names
   that you don't have. Usually short and very
   actionable — often the fastest route to an offer.

6 · WHERE ELSE YOU'D FIT
   Top 10 companies by readiness, with each one's
   single biggest gap.

7 · YOUR EVIDENCE
   What we read and where from:
     - Resume: 14 skills
     - Profile additions: 4 skills
     - LeetCode (verified): 412 solved, rating 1847
   Separated into verified vs self-reported, with a
   note that verified data was used where it was
   higher.

8 · SUGGESTED 12-WEEK PLAN
   Weeks 1-4   SQL fundamentals → level 5
   Weeks 5-9   Cloud & DevOps basics → level 5
   Weeks 10-12 AI foundations → level 3
   Projected readiness after: 34 → 61

9 · HOW THESE NUMBERS WERE CALCULATED
   The formula, stated plainly. The capped-credit
   rule and why it exists. The effort estimates and
   that they are estimates. A note that the level
   estimator is a heuristic, not validated against
   hiring outcomes.
```

### Non-negotiables

- **Section 9 is mandatory.** A tool that scores someone and won't explain how has no business being trusted. Including it is the single strongest signal of engineering maturity in the whole project.
- **Every number traces to evidence.** No unexplained figures anywhere.
- **Section 2 before section 3.** Strengths first, always.
- **Section 8 comes from `plan.json`** if the candidate used the simulator, otherwise from the F3 recommended order.
- Plain language throughout. No category codes, no field names, no JSON.

### Implementation
```python
def generate_report(profile, talent_check, skill_match,
                    company_rankings, plan=None) -> str:
    """Returns Markdown. Pure function — no file I/O."""
```
`storage.py` writes it. `st.download_button` serves it. Keep it a pure function so it's testable and so an HTML renderer can be swapped in later without touching the logic.

---

## Contract changes summary

Only three, all additive and backward compatible:

**1 · New confidence tier** in `contract.py`:
```python
CONFIDENCE_LEVELS = ["verified", "high", "medium", "low"]
CONFIDENCE_WEIGHT = {"verified": 4, "high": 3, "medium": 2, "low": 1}
```

**2 · New block in `profile.json`:**
```json
"coding_profiles": {
  "leetcode": {
    "username": "ananya_r",
    "url": "https://leetcode.com/u/ananya_r",
    "total_solved": 412,
    "easy": 180, "medium": 144, "hard": 88,
    "contest_rating": 1847,
    "fetched_at": "2026-07-20T10:14:00",
    "source": "fetched"
  },
  "hackerrank": null
}
```
`source` is `"fetched"`, `"cached"`, or `"manual"`.

**3 · New fields in `talent_check_result.json`:**
```json
"skillset_gap": [
  {
    "category_code": "DSA",
    "required_level": 8,
    "candidate_level": 8,
    "estimated_level": 6,
    "verified_level": 8,
    "level_source": "verified",
    "gap": false,
    "effort_hours": 0
  }
]
```

Every existing consumer keeps working — nothing was removed or renamed.

---

## Build guidance

**If you have 2 hours:** F1 manual entry only (skip fetching), plus F2. Those two together transform the product.

**If you have 4 hours:** add F4 and F3. F4 is nearly free — it's a loop over code you already have.

**If you have 6 hours:** add F5 in Markdown. Skip PDF.

**What to cut first if time runs out:** HackerRank fetching, then LeetCode fetching (manual entry covers both), then the PDF render, then the F3 three-tab view (ship Recommended order alone).

**What never to cut:** the verified/self-reported distinction. It's the most defensible idea in this addendum, and it costs almost nothing to implement.
