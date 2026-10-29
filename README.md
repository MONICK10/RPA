# Radix Talent Match

Automated resume screening: scores a candidate against a job description,
decides shortlist / review / reject, and reroutes rejected candidates to other
open postings they fit better. Built for the Radix hackathon.

Scoring is fully deterministic. The LLM layer only explains, plans and coaches
on top of numbers the Python already produced — it never computes a score, sets
a level, or invents a requirement.

## Quick start

```powershell
pip install -r requirements.txt
python -m streamlit run app.py        # UI at http://localhost:8501
```

`python -m streamlit` rather than bare `streamlit` because the console script
is not on PATH in every Python install.

Optional: copy `.env.example` to `.env` and add a `GROQ_API_KEY` to switch on
the AI advisor (verdict paragraph, interview prep plan, advisor chat). Every AI
feature has a deterministic fallback, so the app is fully functional with no
keys at all.

## The RPA demo

```powershell
python scripts/reset_demo.py          # restore data/inbox to a known state
python scripts/run_inbox.py           # screen every resume, as the bot does
```

Results land in `data/out/screening_log.csv`, per-candidate folders under
`data/out/runs/`, and decision folders under `data/uipath/`. Rerun
`reset_demo.py` before each demo — `run_inbox.py` empties the inbox as it goes.

Single candidate, with reroute on a reject:

```powershell
python agent.py --resume "data/inbox/Priya Menon.pdf" `
                --jd "data/jds/Microsoft - Data Analyst.pdf" `
                --jd-folder data/jds `
                --summary "data/out/runs/Priya_Menon/summary.json" --quiet
```

`agent.py` prints exactly one `RESULT_JSON` line and never lets a traceback
reach stdout, so UiPath can parse it. `scripts/run_inbox.py` is the reference
implementation of `UIPATH_WORKFLOW.md` for machines without UiPath Studio.

## Tests and calibration

```powershell
python -m pytest tests -q             # 97 tests
python scripts/calibrate.py           # score distribution across all samples
python scripts/calibrate.py --apply   # write config/screening.json thresholds
```

Real match scores in this domain are low (observed 11-34), so fixed cutoffs
like 70 would reject everyone. `calibrate.py` chooses where the lines sit.

## Layout

| Path | What it is |
| --- | --- |
| `app.py` | Streamlit UI |
| `pipeline.py` | runs the 5 scoring modules in order |
| `agent.py` | one command per resume; what the UiPath bot calls |
| `modules/m1`–`m5` | JD analytics, resume parsing, profile builder, talent check, skill matching |
| `modules/m6_screening_agent.py` | the decision and reroute logic |
| `core/llm.py` | AI advisor layer (Groq, OpenAI-compatible) |
| `core/` | extraction, storage, contract validation, reporting |
| `config/` | company map and calibrated thresholds |

## Deployment

Deploys to [Render](https://render.com) as a Web Service via `render.yaml`:
dashboard → New → Blueprint → select this repo, then set `GROQ_API_KEY` in the
service's Environment tab.

Vercel is not a target. Streamlit holds a WebSocket open per viewer and needs a
persistent process; Vercel runs serverless functions with no long-lived server,
so a Streamlit app cannot run there. Render, Railway, Fly.io and Streamlit
Community Cloud all host it as-is.
