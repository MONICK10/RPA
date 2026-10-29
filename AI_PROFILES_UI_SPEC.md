# RADIX Talent Match — AI, Profiles & UI

Single merged spec. Replaces `AI_AND_UI_SPEC.md` and `PROFILE_INTELLIGENCE.md`.

**GitHub integration is parked.** Everything for it is preserved in `PROFILE_INTELLIGENCE.md` Part 1.1 and 2.2 — the architecture here accepts it as a fourth source with no changes required when you add it back.

Three parts:

```
PART A · AI LAYER        Grok, grounded in your own JSON
PART B · PROFILES        LinkedIn · LeetCode · HackerRank
PART C · UI              from dashboard to product
```

---

# PART A · THE AI LAYER

## A.1 · The rule that makes this defensible

**Every LLM call is grounded in the candidate's own JSON. Nothing is generated free-floating.**

```
BAD   → "Give me a study plan for a software engineer"
GOOD  → "Here is this candidate's actual gap data: {json}.
         Here is the company's actual required level: {json}.
         Write a plan that references only these numbers."
```

Scoring stays fully deterministic. The LLM never computes a number, never invents a requirement, never sets a level. It **explains, plans, and coaches** on top of numbers your code produced.

Say this in the demo, in these words:

> "The LLM never touches the score. It explains the score."

That one sentence answers the hallucination question before anyone asks it.

## A.2 · Setup

```bash
pip install openai        # xAI is OpenAI-compatible
```

`.streamlit/secrets.toml` — never commit:
```toml
XAI_API_KEY = "xai-..."
```

`core/llm.py`:
```python
import os, json, hashlib, pathlib
from openai import OpenAI

MODEL = "grok-4.5"          # verify against GET /v1/models for your key
CACHE = pathlib.Path("data/cache")

def _client():
    key = os.getenv("XAI_API_KEY")
    return OpenAI(api_key=key, base_url="https://api.x.ai/v1") if key else None

def ask(system: str, user: str, json_mode: bool = False,
        max_tokens: int = 1200) -> str | None:
    """The single entry point for every LLM call. Returns None on any failure."""
```

Non-negotiables for `ask()`:

- 20-second timeout, one retry, then return `None`
- **Returns `None`, never raises.** Every caller has a deterministic fallback.
- Module-level `LLM_ENABLED` flag driven by a sidebar toggle. Off → every feature below silently uses its fallback.
- Log every prompt and response to `data/out/llm_log.jsonl` — useful for debugging and for showing an evaluator exactly what was sent.
- **Cache on a hash of the input.** `data/cache/llm_<hash>.json`. Same candidate + same company = no second call.

Pre-warm the cache for your demo candidates before presenting. The live demo then never waits on a network call.

## A.3 · The features

Build in this order. Each has a deterministic fallback.

### A1 · Advisor chat — the bot surface

A panel on the results screen. The candidate asks anything about their own result.

```
─ ASK ABOUT YOUR RESULTS ────────────────────────────────
  💬 Why is my company score lower than my role score?

  Your company score is 34 because Acko expects level 6-7
  in AI, Cloud and SQL, and you have no evidence in any of
  them. Your role score of 5 is separate — that posting
  names 18 specific skills and you matched one.

  The useful read: this role is a poor fit, but your systems
  strengths are real. Try the SWE postings instead.

  [ What should I learn first? ] [ Am I ready anywhere? ]
  [ How do I explain my gaps in an interview? ]

  [ Type your question...                        ] [ ask ]
─────────────────────────────────────────────────────────
```

System prompt:
```
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

CANDIDATE PROFILE: {profile_json}
TALENT CHECK:      {talent_check_json}
SKILL MATCH:       {skill_match_json}
COMPANY BAR:       {company_skillsets_json}
```

- Keep the last 6 turns in `st.session_state`.
- Three suggested-question chips, always visible — most users don't know what to ask.
- **Fallback:** the chips still work, answered from templates over the same JSON. The panel never disappears.

### A2 · Verdict paragraph

Replaces the templated "why are these different" note. Two sentences, personal, naming this candidate's actual categories. Cheapest call in the system, and it sits at the top of the screen everyone reads first.

**Build this first — 20 minutes, disproportionate impact.**

**Fallback:** template that names the top three gap categories.

### A3 · Personalised prep plan

The generative task where an LLM clearly beats a template. Takes the effort-ranked gaps and produces a real curriculum.

Force JSON output:
```json
{
  "weeks": [
    {"range": "1-3", "focus": "SQL fundamentals",
     "why": "Fastest gap to close and Acko weights it at 5",
     "topics": ["joins and subqueries", "window functions", "schema design"],
     "milestone": "Write 20 queries against a sample dataset",
     "target_level": 4}
  ],
  "projected_readiness": 61
}
```

Parse it and **render with your own components** — never dump model prose into the UI. Recompute `projected_readiness` yourself; if the model's figure disagrees, use yours and drop theirs.

**Fallback:** deterministic effort ordering with generic topic lists.

### A4 · Interview questions per gap

Highest demo impact per line of code. For each gap, 3 questions at the company's required level.

```
Acko wants SQL at level 5. In an interview that looks like:

1. Find the second-highest salary per department.
2. A query joining three tables is slow — how do you diagnose it?
3. When would you denormalise, and what do you give up?
```

Makes an abstract level concrete. A candidate who couldn't picture "SQL level 5" now can.

**Fallback:** static bank, 3 questions per category per level band.

### A5 · Resume feedback

Grounded in the candidate's own text. Near-zero hallucination risk, high perceived value.

```
Your resume undersells you in two places:

• "Solved 350+ problems" sits under Achievements. That's DSA
  evidence — move it into Skills so it reads as capability.

• Your URL shortener mentions Redis but not the caching
  strategy or the scale. That's your strongest system-design
  signal and it's one line.

Suggested rewrite:
  "Built a horizontally-scalable URL shortener with Redis-backed
   caching, handling N req/s at p99 latency of Xms."
```

Prompt with raw resume text + extracted skills + gap list. Ask specifically: what's present but buried, and what the profile shows that the resume doesn't.

### A6 · Extraction upgrade

Drop-in `llm_extract()` with the same signature as the keyword extractor, keyword fallback on failure. Fixes the `Rag`-inside-`coverage` class of bug entirely.

Force JSON. Validate every `category_code` against `ALL_CODES` before accepting. Invalid entries are discarded individually — never reject the whole response.

### A7 · Profile rewrites

Covered in Part B.3 — the LinkedIn headline, About section, and repo description rewrites. Same grounding rule.

## A.4 · Demo safety

- Pre-warm the cache for both demo candidates
- Sidebar toggle "AI features" defaults **on** for the demo, every feature has a fallback
- If a call hangs, the deterministic fallback renders after 20s — never an unresolving spinner
- Keep one screenshot of the advisor answering, in case the network dies entirely

---

# PART B · PROFILES

Three sources. Two distinct outputs from them.

```
LinkedIn ────┐
LeetCode ────┼──►  ① EVIDENCE      raises verified skill levels
HackerRank ──┘     ② VISIBILITY    "can a recruiter tell?"
```

① makes the score more accurate. ② is the feature nobody else has.

## B.1 · Acquisition

Each platform is a different problem. Don't treat them uniformly.

### LinkedIn — upload, don't scrape

No public profile API, and their terms prohibit scraping. Scraping it in a project you're presenting is a bad look and it breaks constantly.

**The correct approach, which is also the better one:** LinkedIn lets any user export their own profile as a PDF (`your profile → More → Save to PDF`). The candidate uploads that file.

- Legal, stable, works offline
- **Reuses your existing `extract_text()` and resume parser** — almost no new code
- Richer than scraping: includes the About section, full project descriptions, and endorsements

Add a parser mode that recognises LinkedIn's PDF structure (Experience / Education / Licenses & Certifications / Skills) and pulls the **headline** and **About** section separately — those two drive the visibility advice in B.3.

In the UI, one line of instruction removes all friction:
> *"LinkedIn → your profile → More → Save to PDF, then upload it here."*

### LeetCode — public GraphQL

```
POST https://leetcode.com/graphql
{ matchedUser(username: "...") {
    submitStats { acSubmissionNum { difficulty count } }
    profile { ranking reputation }
} }
```

Plus `userContestRankingInfo` for rating. Unofficial but stable for years.

### HackerRank — manual entry primary

No reliable public API; badges render client-side. Make manual entry the main path — a small form for stars per track. Treat fetching as a bonus that may break.

### The pattern for all three

```python
def fetch_profile(platform: str, handle: str) -> dict:
    """Returns {"status": "fetched"|"cached"|"manual"|"failed",
                "data": {...}, "error": str|None}"""
```

- 5-second timeout, one retry, graceful failure
- Cache every success to `data/cache/{platform}_{handle}.json`
- **Manual entry always available** under every field
- Failure reads *"Couldn't reach LeetCode. Enter your numbers below or try again."*
- Pre-cache your demo profiles before presenting

## B.2 · Evidence — profiles into levels

### The confidence ladder

```
verified    weight 4    LeetCode — machine-checkable
declared    weight 3    LinkedIn — self-written but public and accountable
high        weight 3    resume, strong evidence
medium      weight 2
low         weight 1
```

`declared` sits between deliberately: a LinkedIn profile is self-written, but it's public and a recruiter reads it, so it carries more weight than a private resume claim.

### LeetCode → levels

Touches **DSA, COD, APTI only.** These are exactly the three a resume evidences weakly and a coding platform evidences strongly. It must not touch Cloud or Communication — that would be noise.

**DSA** — volume, adjusted for difficulty and contests:

| Total solved | Base |
|---|---|
| < 50 | 3 |
| 50–149 | 5 |
| 150–299 | 6 |
| 300–499 | 7 |
| 500+ | 8 |

Then: hard ≥ 15% of total → **+1** · contest rating ≥ 1800 → **+1**, ≥ 2100 → **+2**. Cap 10.

**COD** — `min(8, 3 + total_solved // 100)`

**APTI** — rating ≥ 1600 → 6 · ≥ 1900 → 7 · ≥ 2200 → 8. No contests → `min(7, DSA − 1)`.

### HackerRank → levels

Map stars per track. 5-star Problem Solving → DSA 7. 5-star language track → COD 7. Gold badge → +1. **Treat as a floor, not an override** — HackerRank stars are easier to earn than LeetCode volume.

### LinkedIn → levels

Skills and projects extracted at `declared` confidence, merged into the profile exactly like resume skills. No special level mapping — it's another document, not a metric source.

### The merge rules

```python
final = max(estimated_from_resume, verified_from_platform)
```

Two hard rules, both worth stating out loud in the demo:

**Verified evidence raises a level, never lowers one.** A candidate with strong private or project work shouldn't be punished for a thin LeetCode.

**Cap total platform lift at +3 per category.** Otherwise grinding easy problems outscores real engineering.

Record both numbers so the report can show `estimated 6 → verified 8`.

### UI on the profile screen

```
─ CODING PROFILES (optional) ────────────────────────────
  Verified practice data. Replaces our estimate for Data
  structures, Coding and Aptitude with your actual numbers.

  LeetCode     [ leetcode.com/u/ananya_r      ] [ fetch ]
  HackerRank   [ paste your profile URL        ] [ fetch ]
  LinkedIn     [ upload your profile PDF       ] [ browse ]
               LinkedIn → your profile → More → Save to PDF

  ✓ LeetCode: 412 solved · 88 hard · rating 1847
    → Data structures raised from 6 to 8 (verified)
─────────────────────────────────────────────────────────
```

All optional. Empty is a valid state, never a warning. After a fetch, show what was found **and what it changed** — that line is the whole payoff.

## B.3 · Visibility — the original feature

Readiness asks *can you do the job.* Visibility asks *can a recruiter tell.*

A candidate can be genuinely ready and completely invisible. Separate problem, much faster fix, and no other tool addresses it.

### Placement

A card **below** the two scores. Not a third score — the two-score thesis stays intact. A **checklist**, framed as fixes rather than a grade.

```
─ HOW YOU LOOK TO A RECRUITER ───────────────────────────
  You have the skills. Here's what your profiles don't show.

  LinkedIn                                      3 fixes
  ✕  Headline reads "CSE Student at Karunya" — say what
     you build, not where you study
  ✕  About section is empty
  ✕  Skills list is missing Docker and Redis, both of
     which appear in your own projects

  LeetCode                                      1 fix
  ✕  No real name set — recruiters can't connect this
     profile to your application
  ✓  412 solved with 21% hard — strong signal

  [ show me the fixes ]
─────────────────────────────────────────────────────────
```

### The checks — deterministic, no LLM

**LinkedIn**

| Check | Why it matters |
|---|---|
| Headline is more than "Student at X" | It's the line in every search result |
| About section non-empty | Only place you control the narrative |
| Projects section populated | Where technical depth lives |
| Skills include everything in your own profile | Recruiter filters run on this field |
| **Skills include the target JD's named skills** | Direct keyword match on how you're found |

That last check is the sharpest thing you have — you already extracted the JD's skills, so you can name exactly which keywords their LinkedIn is missing for a specific job.

**LeetCode / HackerRank** — profile public, real name set, contest participation.

### The fixes — where the LLM earns its place

Grounded entirely in the candidate's own text.

**Headline rewrite:**
```
Now:       "CSE Student at Karunya Institute of Technology"
Suggested: "Backend engineer — distributed systems, Redis,
            multithreaded C++ · Building at scale"

Why: your headline says where you are, not what you do.
Recruiters search by capability.
```

**About section draft** — 3 sentences from projects and preferred roles, in the candidate's own register. Add a copy button and they'll actually use it.

### The JD-targeted version — the strongest variant

Once a JD is loaded:

```
─ FOR THIS ROLE SPECIFICALLY ────────────────────────────
  This posting names 18 skills. Your LinkedIn shows 4.

  Missing from your Skills section, but present in your work:
    Docker · Redis · CI/CD · System design

  Add these four and you'll surface in recruiter searches
  for this role. You already have the evidence.
─────────────────────────────────────────────────────────
```

Closes the loop between JD Analytics and something the candidate fixes in five minutes.

## B.4 · The evidence ledger

One view showing every claim and its source. Put it on the profile screen and in the report.

```
─ WHAT WE READ ──────────────────────────────────────────
  Resume             14 skills       self-reported
  Profile additions   4 skills       self-reported
  LinkedIn PDF        6 skills       declared
  LeetCode           412 solved      verified   ✓

  Coding             8  ← LeetCode: 412 solved
  Data structures    8  ← LeetCode: 88 hard, rating 1847
  Operating systems  8  ← resume: multithreaded scheduler
  Communication      6  ← resume: mentors juniors on DSA
  AI                 0  ← no evidence in any source
─────────────────────────────────────────────────────────
```

**Every level traces to its source.** This is what makes the tool defensible rather than a black box, and it's genuinely uncommon. Lead with it if anyone asks how you avoid arbitrary scoring.

---

# PART C · THE UI

## C.1 · What's wrong now

The current screens show default Streamlit: raw dataframes, default blue bars, `category_code` visible to users, JSON download buttons in the main flow. That reads as a debug tool.

The fix isn't decoration. It's **hierarchy** — deciding what the eye hits first, second, third, and making everything else recede.

## C.2 · Direction

**Instrument panel meets report card.** Precise, dense where it needs to be, calm everywhere else.

The two score cards are the hero. Everything else is quieter. If a third element competes visually, mute it or remove it.

### Tokens

```css
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
--warn:        #F5C451;
--bad:         #F0665C;

/* data viz */
--bar-track:   #232B3A;
--bar-req:     #4A5568;   /* required — muted, it's the backdrop */
--bar-cand:    #F0A030;   /* candidate — accent, it's the subject */
```

**One accent, one job.** Amber means "this is you" or "this is the action." Nothing decorative is amber.

### Type

```
UI / data:  'Geist', 'Inter', system-ui     14px base, 1.55 line-height
Display:    'Instrument Serif', Georgia     the two big scores, report headings
Mono:       'Geist Mono', ui-monospace      levels, hours, any figure in a table
```

The serif on the two big numerals is the highest-leverage choice here. It stops them reading as dashboard metrics and starts them reading as a verdict.

```
Score numeral    72px   Instrument Serif
Card eyebrow     11px   Geist 600 · 0.08em tracking · uppercase · --text-faint
Section heading  15px   Geist 600
Body             14px   Geist 400
Label / helper   12.5px Geist 400 · --text-mute
Table figures    13px   Geist Mono · tabular-nums
```

Sentence case everywhere except card eyebrows.

### Space and shape

- 8px base grid. Card padding 24px. 32px between sections.
- Radius 10px on cards, 6px on chips and buttons.
- **No shadows.** 1px borders only — shadows on dark surfaces look cheap.
- Max content width 1120px, centred.

## C.3 · The results screen

```
┌────────────────────────────────────────────────────────────┐
│  Ananya Rao                                                │
│  Google LLC · Software Engineer · 20 July                  │
│                                                            │
│ ┌──────────────────────────┐ ┌──────────────────────────┐ │
│ │ COMPANY READINESS        │ │ ROLE FIT                 │ │
│ │   77                     │ │   88                     │ │
│ │   ───────────────        │ │   ───────────────        │ │
│ │   Nearly ready           │ │   Strong match           │ │
│ │   9 of 12 skillsets met  │ │   2 skills missing       │ │
│ └──────────────────────────┘ └──────────────────────────┘ │
│                                                            │
│  Google's overall bar includes AI, Cloud and SQL, which    │
│  this role doesn't test. You're a strong fit for this      │
│  posting, with a gap for the company more broadly.         │
├────────────────────────────────────────────────────────────┤
│  WHERE YOU STAND                                           │
│  Coding             ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│      9 · 9   ✓    │
│  Data structures    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░│      8 · 9   −1   │
│  AI                 ░░░░░░░░░░░░░░░░░░│      0 · 7   −7   │
│                                        ↑ required          │
├────────────────────────────────────────────────────────────┤
│  WHERE TO FOCUS      [Recommended][Impact][Quickest]       │
│  1  SQL             +6.5 readiness    ~60 hrs              │
│  2  Cloud & DevOps  +6.5 readiness    ~75 hrs              │
├────────────────────────────────────────────────────────────┤
│  HOW YOU LOOK TO A RECRUITER            LinkedIn · 3 fixes │
├────────────────────────────────────────────────────────────┤
│  ASK ABOUT YOUR RESULTS                            [ AI ]  │
└────────────────────────────────────────────────────────────┘
```

Details that matter:

- **Required level is a tick mark on the track, not a second bar.** Two overlapping bars is what made the current chart unreadable. One filled bar = the candidate. A vertical line = the bar to clear.
- **Never show `category_code` to a user.** "Data structures", not "DSA". Codes live in developer view.
- **Met rows are quiet.** `--text-mute`, small ✓. Gap rows get full `--text`, with the gap figure in `--warn` or `--bad` by size.
- **No dataframes on this screen.** Build rows as HTML. `st.dataframe` always looks like a debug view.
- **Download buttons move to the bottom**, one muted row. They're not part of the reading flow.

## C.4 · Streamlit implementation

```python
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Instrument+Serif&display=swap" rel="stylesheet">
<style>
  #MainMenu, footer, header {visibility: hidden;}
  .stDeployButton {display: none;}
  .block-container {max-width: 1120px; padding-top: 2rem;}
  html, body, [class*="css"] {font-family: 'Geist', system-ui;}
  /* tokens as CSS vars, then component classes */
</style>
""", unsafe_allow_html=True)
```

- One CSS block at app start. Don't scatter styles.
- Build cards, bars and chips as **HTML strings in Python**, rendered in a single `st.markdown`. Native components are for inputs only.
- `st.metric` cannot carry the hero scores. Hand-write them.
- Bars are `<div>`s with percentage widths. No chart library on this screen — faster and fully controllable.
- Advisor chat: `st.chat_message` and `st.chat_input` are genuinely good. Use them.
- Every `st.dataframe` goes behind the developer toggle.

---

# BUILD ORDER

```
 1  CSS block — fonts, tokens, hide Streamlit chrome      20 min  ★ biggest visual jump
 2  Two hero score cards, hand-built HTML                 30 min
 3  Gap bars with required tick mark                      30 min
 4  A2 · verdict paragraph                                20 min
 5  A1 · advisor chat panel                               45 min
 6  LeetCode fetch + evidence mapping                     40 min
 7  Evidence ledger                                       30 min
 8  LinkedIn PDF upload (reuses your parser)              40 min
 9  Visibility checklist, deterministic                   60 min
10  B.3 · LLM profile rewrites                            45 min
11  JD-targeted keyword gap                               20 min
12  A4 · interview questions                              30 min
13  A3 · prep plan                                        45 min
14  A5 · resume feedback                                  30 min
15  HackerRank manual entry                               20 min
16  A6 · LLM extraction upgrade                           45 min
```

**Steps 1–5 in under two and a half hours and the app stops looking like a script with a frontend.**

**If you build only four more things after that:** LeetCode evidence, the evidence ledger, the visibility checklist, and the JD-targeted keyword gap. Those four are where the originality is.

---

# CONTRACT CHANGES

All additive, all backward compatible.

**1 · Confidence tiers** in `contract.py`:
```python
CONFIDENCE_LEVELS = ["verified", "declared", "high", "medium", "low"]
CONFIDENCE_WEIGHT = {"verified": 4, "declared": 3, "high": 3,
                     "medium": 2, "low": 1}
```

**2 · New block in `profile.json`:**
```json
"external_profiles": {
  "leetcode": {
    "username": "ananya_r",
    "total_solved": 412, "easy": 180, "medium": 144, "hard": 88,
    "contest_rating": 1847,
    "fetched_at": "2026-07-20T10:14:00",
    "source": "fetched"
  },
  "hackerrank": null,
  "linkedin": {
    "headline": "...", "about": "...", "skills": [...],
    "source": "pdf_upload"
  }
}
```
`source` is `"fetched"`, `"cached"`, `"manual"`, or `"pdf_upload"`.

**3 · New fields in `talent_check_result.json`:**
```json
{
  "category_code": "DSA",
  "required_level": 8,
  "candidate_level": 8,
  "estimated_level": 6,
  "verified_level": 8,
  "level_source": "verified",
  "evidence": "LeetCode: 412 solved, 88 hard, rating 1847",
  "gap": false,
  "effort_hours": 0
}
```

**4 · New output file:** `visibility_result.json` — per-platform check results and generated fixes.

Nothing removed, nothing renamed. Every existing consumer keeps working.

---

# LIMITATIONS — say these before you're asked

- **Platform activity is not skill.** Grinding easy problems isn't engineering. Mitigated by the +3 cap and by weighting difficulty and contests over raw volume, but not solved.
- **Private and company work is invisible.** Someone with two years of closed-source production experience may show almost nothing publicly. The merge rule protects them — their resume estimate still stands.
- **LinkedIn is self-written.** `declared`, not `verified` — which is exactly why that tier exists.
- **Platform APIs are unofficial** and can change. Everything degrades to manual entry.
- **Visibility advice is opinion.** It reflects common recruiter behaviour, not measured outcomes. Frame it as suggestions, never rules.
- **The LLM can still be wrong** in its explanations even when the numbers are right. Every generated section is labelled, and the numbers beneath it are computed deterministically and independently verifiable.

---

# WHAT TO SAY

**On the AI layer:**
> "Scoring is fully deterministic — the LLM never computes a number. Every call is grounded in the candidate's own assessment JSON, so it can only explain and plan on top of data our code produced. Every AI feature has a deterministic fallback. Turn the API off and the app still works end to end."

**On profiles:**
> "A resume saying '350+ problems solved' is a claim. A LeetCode profile is a fact. So we added a confidence tier above 'high' called 'verified' — the only tier a candidate can't inflate. And verified evidence raises a level, never lowers one, because someone with strong private work shouldn't be punished for a thin public profile."

**On visibility:**
> "Most readiness tools stop at 'are you good enough.' This one also answers 'can a recruiter tell.' A candidate can be genuinely ready and completely invisible — and that's a separate problem with a much faster fix."

**On the evidence ledger:**
> "Every level traces back to the exact evidence that produced it. That's how the tool stays defensible instead of being a black box that hands you a number."
