# RADIX Talent Match — UI Specification

Supersedes Section 9 of `RADIX_TALENT_MATCH_BUILD_SPEC.md`. The five modules, the data contract, and the scoring logic do not change at all — only what the user sees.

---

## 1. The core problem with the current UI

Six tabs named after the five modules exposes the *architecture*, not the *product*. A candidate does not want to "run JD Analytics." They want to know if they're ready.

**Reframe: the app is a 3-step journey, not a 6-module control panel.**

```
BEFORE (developer's model)          AFTER (user's model)
─────────────────────────           ────────────────────
Tab: JD Analytics                   Step 1 · Upload
Tab: Resume Parsing        ──►        both files, one button
Tab: Profile Builder                Step 2 · Your profile
Tab: Talent Check                     review and add what's missing
Tab: Skill Matching                 Step 3 · Your results
Tab: Full Pipeline                    two scores, one gap plan
```

The five modules still run. They're just no longer the navigation.

**Keep the module view — move it.** Add a sidebar toggle, "Developer view." When on, it reveals the old six tabs plus raw JSON and the ✅/⬜/❌ module status bar. This is how you prove the architecture to an evaluator without making a candidate look at it. Default: off.

---

## 2. Screen flow

### Progress stepper — persistent, top of every screen

```
  ●━━━━━━━━━━━●━━━━━━━━━━━○
Upload      Profile     Results
 done        active      locked
```

- Completed step: filled circle, accent colour, clickable to go back
- Active step: filled circle, ring around it
- Locked step: hollow circle, muted, not clickable
- Height ~64px, sits under the header, never scrolls away

This replaces the module status bar for normal users. It is the same information — how far along are we — expressed in the user's language.

---

### Screen 1 · Upload

Single question: *what job, and who are you?*

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   Find out if you're ready.                              │
│   Upload a job description and your resume. We'll        │
│   show you exactly what's missing.                       │
│                                                          │
│   ┌────────────────────┐  ┌────────────────────┐        │
│   │  📄                │  │  👤                │        │
│   │  Job description   │  │  Your resume       │        │
│   │                    │  │                    │        │
│   │  Drop a PDF or     │  │  Drop a PDF or     │        │
│   │  DOCX here         │  │  DOCX here         │        │
│   │                    │  │                    │        │
│   │  or pick a sample ▾│  │  or pick a sample ▾│        │
│   └────────────────────┘  └────────────────────┘        │
│                                                          │
│   Target company                                         │
│   [ Google LLC (Subsidiary of Alphabet Inc.)        ▾ ]  │
│   Auto-detected from the job description. Change if wrong.│
│                                                          │
│              [  Analyse my fit  →  ]                     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

Requirements:

- Two dropzones side by side, equal weight. Dashed 2px border, generous padding, hover state.
- **Each dropzone has a "pick a sample" dropdown** listing the 6 sample JDs / 4 sample resumes. This is essential for the demo — you must be able to switch candidates in two clicks, live, without hunting for files.
- Once a file lands, the dropzone collapses into a filled state: filename, page count or character count, a green tick, and a small "replace" link.
- Company dropdown auto-fills from JD detection but stays editable. Helper text explains why.
- The primary button stays disabled until both files are present. Disabled state must look disabled, not broken.
- On click: show a progress sequence, not a spinner —
  ```
  Reading the job description...   ✓ 22 skills found
  Reading your resume...            ✓ 14 skills found
  Building your profile...          ✓
  Checking against Google...        ✓
  Matching to this role...          ✓
  ```
  Each line appears as its module completes. This is the module status system, re-skinned in plain language. It is also the most convincing three seconds of the demo — the judges watch five modules fire in sequence.

---

### Screen 2 · Your profile

Framing matters. This is not a form to fill. It is: *here's what we found — what did your resume leave out?*

```
┌──────────────────────────────────────────────────────────┐
│  We read your resume. Add what it missed.                │
│  Resumes undersell people. Hackathons, certifications    │
│  and side projects all count — add them here.            │
│                                                          │
│  Ananya Rao                          ✎ edit              │
│  B.Tech CSE, 2026 · CGPA 8.6                             │
│                                                          │
│  ─ Skills we found (14) ──────────────────────────────   │
│                                                          │
│   Coding          C++ ×  Python ×  Java ×                │
│   DSA             Data structures ×  Algorithms ×        │
│   OS              Operating systems ×  Multithreading ×  │
│   Networking      Computer networks ×                    │
│   ...                                                    │
│                                    [ + add a skill ]     │
│                                                          │
│  ─ What else have you done? ──────────────────────────   │
│                                                          │
│   Hackathons        [ National 24-hour hackathon —     ] │
│                     [ finalist                         ] │
│   Internships       [ Backend intern, product startup  ] │
│   Certifications    [ none yet                         ] │
│   Preferred roles   [ Software Engineer × ] [ Backend × ]│
│                                                          │
│              [  ← back  ]    [  See my results  →  ]     │
└──────────────────────────────────────────────────────────┘
```

Requirements:

- Skills render as **removable chips grouped by category**, not a raw table. Chips show the skill name with an `×`. Category name sits to the left as a muted label.
- Chips are colour-coded by confidence: solid = high, outlined = medium, dashed = low. One legend line explains it.
- "Add a skill" opens an inline row: text field + category dropdown. New skills get confidence `high`, evidence `self-reported`.
- Free-text areas for hackathons, internships, certifications — one item per line, with placeholder text showing the expected format.
- Preferred roles as chips with an add field.
- Everything pre-filled from resume parsing. Empty fields show a helpful placeholder, never a blank box.
- **Explain the payoff inline:** a small note under the "what else" section — *"These feed into your Aptitude, Communication and Software Engineering scores."* It tells the user why the effort is worth it.

---

### Screen 3 · Your results

The payoff screen. Two scores, then the plan.

```
┌──────────────────────────────────────────────────────────┐
│  Ananya Rao  ·  Google LLC  ·  Software Engineer         │
│                                                          │
│  ┌─────────────────────┐   ┌─────────────────────┐      │
│  │  COMPANY READINESS  │   │  ROLE FIT           │      │
│  │                     │   │                     │      │
│  │        77           │   │        88           │      │
│  │      ╭─────╮        │   │      ╭─────╮        │      │
│  │      │ ring │       │   │      │ ring │       │      │
│  │      ╰─────╯        │   │      ╰─────╯        │      │
│  │   Nearly ready      │   │   Strong match      │      │
│  │                     │   │                     │      │
│  │  vs Google's bar    │   │  vs this posting    │      │
│  │  across 12 skillsets│   │  2 skills missing   │      │
│  └─────────────────────┘   └─────────────────────┘      │
│                                                          │
│  ℹ Why are these different?                              │
│    Google's overall bar includes AI, Cloud and SQL.      │
│    This particular role doesn't test them. You're a      │
│    strong fit for this job, with a gap for the company   │
│    in general.                                           │
│                                                          │
│  ─ Where you stand ───────────────────────────────────   │
│                                                          │
│   Coding            ████████████████████ 9 / 9   ✓       │
│   DSA               ██████████████████░░ 8 / 9   −1      │
│   OOD               ████████████████████ 8 / 6   ✓       │
│   Aptitude          ████████████████████ 7 / 6   ✓       │
│   Communication     ████████████████████ 6 / 6   ✓       │
│   AI                ░░░░░░░░░░░░░░░░░░░░ 0 / 7   −7  ▲   │
│   Cloud / DevOps    ░░░░░░░░░░░░░░░░░░░░ 0 / 5   −5  ▲   │
│   SQL               ░░░░░░░░░░░░░░░░░░░░ 0 / 5   −5  ▲   │
│   Software eng      ████████████████████ 8 / 7   ✓       │
│   System design     ████████████████████ 8 / 6   ✓       │
│   Networking        ████████████████████ 8 / 5   ✓       │
│   Operating systems ████████████████████ 8 / 6   ✓       │
│                                                          │
│  ─ Your plan ─────────────────────────────────────────   │
│                                                          │
│   To close the gap for Google                            │
│   1  AI / ML fundamentals          biggest gap, −7       │
│   2  Cloud and DevOps basics       −5                    │
│   3  SQL and data modelling        −5                    │
│                                                          │
│   To land this specific role                             │
│   1  CI/CD concepts                named in the JD       │
│   2  Testing strategy              named in the JD       │
│                                                          │
│  [ ← edit profile ]  [ try another company ▾ ]  [ ↓ PDF ]│
└──────────────────────────────────────────────────────────┘
```

Requirements:

- **Two score cards, equal size, side by side.** Not one blended number. The visual separation is the product thesis made physical.
- A ring or arc for each score, not a bar. Colour by band: ≥85 green, 70–84 amber, 50–69 orange, <50 red.
- **The "why are these different" note is mandatory** and must be generated, not hardcoded — it names the actual categories causing the divergence. This single paragraph is what an evaluator will remember.
- The 12-skillset view: horizontal bars, candidate fill against a required marker. `✓` when met, `−N` when short. A `▲` flag on the top three gaps.
- **"Your plan" is the most important section on the screen.** Two ranked lists — company gaps from Talent Check, role gaps from Skill Matching. Numbered, because they are genuinely a priority order.
- "Try another company" re-runs Talent Check only, in place, without re-uploading. Two seconds, and it makes the tool feel alive during the demo.
- Download as PDF is optional. Build only if everything else is done.

---

## 3. Visual direction

Take the palette from the RADIX/talencia documents so the tool looks like it belongs to the platform, not like a generic template.

```
--navy-900   #1B3A57   headers, primary text, filled bars
--navy-700   #2C5578   secondary structure
--amber-500  #E8890C   primary accent, buttons, active step
--amber-100  #FCEDD6   accent fills, chip backgrounds
--paper      #FBFAF7   page background
--surface    #FFFFFF   cards
--border     #E4E1DA   hairlines
--text-mute  #6B6963   labels, helper text
--green-600  #2E7D5B   met / success
--red-600    #C0392B   gap / missing
```

Type:
- Headings and scores: one weight up from body, navy, sentence case. The two big scores are the only oversized numerals on the page — 56px, tabular figures.
- Body: 15px, line-height 1.6.
- Labels and helper text: 13px, `--text-mute`.
- **Sentence case everywhere.** No ALL CAPS except the two small card eyebrows.

Structure:
- White cards on `--paper`, 1px `--border`, 12px radius, no shadows.
- Generous vertical rhythm — 2rem between sections, 1.25rem inside cards.
- One accent colour doing one job: amber = "this is the action or the thing to look at." Nothing else is amber.

**The signature element is the two-score card pair.** Everything else stays quiet so that comparison lands. Resist adding a third score, a radar chart, or a leaderboard.

---

## 4. Streamlit implementation notes

Streamlit will not look like this out of the box. It gets ~85% of the way there with:

1. **`.streamlit/config.toml`** — set the theme:
   ```toml
   [theme]
   primaryColor = "#E8890C"
   backgroundColor = "#FBFAF7"
   secondaryBackgroundColor = "#FFFFFF"
   textColor = "#1B3A57"
   font = "sans serif"
   ```

2. **One `st.markdown(..., unsafe_allow_html=True)` CSS block** at app start. Hide the Streamlit chrome (`#MainMenu`, `footer`, the deploy button), widen the container, restyle cards and buttons.

3. **Screens via `st.session_state.step`**, not `st.tabs`. A tab bar is the thing being removed.
   ```python
   if st.session_state.step == 1: render_upload()
   elif st.session_state.step == 2: render_profile()
   else: render_results()
   ```

4. **Score rings** — render as inline SVG inside `st.markdown`. A `st.metric` will not carry this screen.

5. **Skill chips** — build the HTML string in Python and render in one `st.markdown` call. Removal via a small `×` link that sets a session-state key. Do not use `st.multiselect`; it looks like a form control, not a profile.

6. **The bar list** — inline HTML divs with percentage widths. Cleaner and faster than a chart library here, and it renders instantly.

7. Developer view stays as `st.tabs` inside `if st.sidebar.toggle("Developer view")`. Zero effort, and it preserves everything already built.

**If time is short, cut in this order:** PDF download → score rings (fall back to large numerals) → chip removal (make skills read-only) → "try another company." Never cut the two-score card pair or the plan section — those are the product.

---

## 5. Copy rules

- Speak to the candidate, not about the system. "You're missing CI/CD," not "Skill gap detected in category CLOUD."
- Name things as the user recognises them: "Job description," not "JD payload." "Your profile," not "Profile Builder output."
- Empty states are invitations: "No certifications yet — add any you're working towards."
- Errors say what happened and what to do: "We couldn't read text from that PDF. It may be a scanned image — try a text-based PDF or paste the description instead."
- Buttons name their outcome: "Analyse my fit," "See my results." Never "Submit" or "Run."
- Never show a category code (`CLOUD`, `SYSD`) to a normal user. Always the full name. Codes belong in developer view only.

---

## 6. Acceptance checks

- [ ] A first-time user reaches a result in two clicks from landing, using sample files
- [ ] Nothing on screens 1–3 mentions modules, JSON, pipelines, or category codes
- [ ] The two scores are visually separate and equally weighted
- [ ] The "why are these different" note is generated from the actual data, and reads correctly for a candidate where the two scores are close as well as far apart
- [ ] Switching sample candidates takes two clicks and visibly changes every number on screen 3
- [ ] Developer view toggle still exposes the 6 module tabs, raw JSON, and the ✅ status bar
- [ ] No Streamlit branding, hamburger menu, or footer visible
- [ ] Works at 1280px wide; degrades to single column below 900px
