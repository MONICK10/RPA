# run_inbox.py - screen every resume in data/inbox, exactly as the UiPath bot
# will. This is the reference implementation of the workflow in
# UIPATH_WORKFLOW.md: same decision, same summary file, same folder moves, same
# continue-on-error behaviour. Two reasons it exists:
#
#   1. the demo is runnable (and the R6 verify is checkable) on a machine with
#      no UiPath Studio installed
#   2. the UiPath teammate has something working to compare their build against
#
# It is NOT a replacement for the bot. It does not write the Excel report or
# send mail - those are UiPath activities 10 to 12.
#
#   python scripts/run_inbox.py
#   python scripts/run_inbox.py --jd "data/jds/Microsoft - Software Engineer.pdf"
#
# Why this is Python and not PowerShell: the first version was a .ps1 that
# spawned agent.py once per file. Run as a redirected child process on Windows
# PowerShell 5.1 it terminated silently - exit code 0, no error record, no
# trapped exception - on the iteration where agent.py returns a non-zero exit
# code for the unreadable file. The same loop ran fine inline, so the fault is
# in PS 5.1's process spawning, not the logic (PROGRESS.md Section D #16).
# Calling screen_resume() in-process removes process spawning, stream
# redirection and console-encoding from the demo path altogether. reset_demo.ps1
# stays PowerShell because R6 asks for it by name, and it spawns nothing.

import argparse
import logging
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# pypdf logs "invalid pdf header" / "EOF marker not found" for the deliberately
# unreadable file. The failure is already captured in that candidate's summary
# reason and in the audit log, so the console copy is noise that makes a live
# demo look broken. Quieted here in the demo runner only - never in a module.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent import _slug, screen_resume                              # noqa: E402
from core.storage import move_file                                   # noqa: E402

# decision -> destination folder. Every decision the agent can return has a
# home; anything unrecognised is treated as an exception rather than left in
# the inbox, so a file can never be silently skipped.
FOLDER_FOR = {
    "shortlist": "Shortlisted",
    "review": "Review",
    "reroute": "Rerouted",
    "reject": "Rejected",
    "exception": "Exceptions",
}

# Everything HR dropped gets screened, whatever the extension. UiPath activity 2
# is Directory.GetFiles with no filter, and an unscreenable file must land in
# Exceptions with a reason - not be silently skipped and left in the inbox.
SKIP_NAMES = (".gitkeep",)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Screen every resume in the inbox, as the UiPath bot will.")
    parser.add_argument("--inbox", default="data/inbox")
    parser.add_argument("--jd", default="data/jds/Microsoft - Data Analyst.pdf")
    parser.add_argument("--jd-folder", default="data/jds")
    parser.add_argument("--out-root", default="data/out/runs")
    parser.add_argument("--uipath", default="data/uipath")
    args = parser.parse_args()

    inbox = pathlib.Path(args.inbox)
    if not inbox.is_dir():
        print(f"{args.inbox} is missing. Run scripts/reset_demo.ps1 first.")
        return 1

    files = sorted(
        (p for p in inbox.iterdir() if p.is_file() and p.name not in SKIP_NAMES),
        key=lambda p: p.name,
    )
    if not files:
        print(f"{args.inbox} is empty. Run scripts/reset_demo.ps1 first.")
        return 0

    print()
    print(f"Screening {len(files)} file(s) against {pathlib.Path(args.jd).name}")
    print()

    rows = []
    for path in files:
        run_dir = pathlib.Path(args.out_root) / _slug(path.stem)

        # --- the Try Catch around the loop body (UiPath activity 4) --------
        try:
            # as_posix: a failure reason can quote the path it was handed, and
            # forward slashes keep it safe to paste into UiPath or a CSV cell
            summary = screen_resume(
                path.as_posix(), args.jd, jd_folder=args.jd_folder,
                out_root=args.out_root, quiet=True,
            )
        except Exception as e:                      # noqa: BLE001 - rule 6
            summary = {
                "candidate_name": "", "readiness": None, "match": None,
                "decision": "exception",
                "reason": f"The runner could not process this file: "
                          f"{type(e).__name__}: {e}",
                "rerouted_to_role": "",
            }

        decision = summary.get("decision", "")
        if decision not in FOLDER_FOR:
            decision = "exception"
        folder = FOLDER_FOR[decision]

        # --- Switch on decision -> Move File (UiPath activity 7) ----------
        try:
            moved_to = move_file(str(path), str(pathlib.Path(args.uipath) / folder))
        except Exception as e:                      # noqa: BLE001
            moved_to = f"NOT MOVED ({type(e).__name__}: {e})"

        # --- Add Data Row (UiPath activity 8) -----------------------------
        rows.append({
            "file": path.name,
            "name": summary.get("candidate_name") or "",
            "readiness": summary.get("readiness"),
            "match": summary.get("match"),
            "decision": decision,
            "moved_to": folder,
            "routed_to": summary.get("rerouted_to_role") or "",
            "run_dir": run_dir.as_posix(),
            "location": moved_to,
        })
        print(f"  {path.name:<26} {decision:<10} -> {folder}")

    print()
    header = (f"{'file':<26} {'name':<20} {'readiness':>9} {'match':>6} "
              f"{'decision':<10} {'moved to':<12} routed to")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['file']:<26} {r['name']:<20} {str(r['readiness']):>9} "
              f"{str(r['match']):>6} {r['decision']:<10} {r['moved_to']:<12} "
              f"{r['routed_to'] or '-'}")

    print()
    print("Counts per decision:")
    for decision in sorted(FOLDER_FOR):
        n = sum(1 for r in rows if r["decision"] == decision)
        if n:
            print(f"  {decision:<10} {n}")
    distinct = sorted({r["decision"] for r in rows})
    print()
    print(f"Distinct decisions: {len(distinct)} -> {distinct}")
    print()
    print("Audit log: data/out/screening_log.csv")
    print("Reset with: powershell -ExecutionPolicy Bypass -File scripts/reset_demo.ps1")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
