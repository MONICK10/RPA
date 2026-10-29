# reset_demo.py - put the RPA demo back to a known state, in one command.
#
# A demo has to be repeatable. The bot moves resumes out of data/inbox into
# data/uipath/<Decision>, writes per-resume folders under data/out/runs, and
# appends to the audit log. After one run the inbox is empty, so a second run
# screens nothing. This undoes all of that.
#
#   powershell -ExecutionPolicy Bypass -File scripts/reset_demo.ps1   (wrapper)
#   python scripts/reset_demo.py                                      (direct)
#   python scripts/reset_demo.py --dry-run
#
# What it does:
#   1. restores data/inbox      from data/inbox_seed  (the canonical copy)
#   2. empties  data/out/runs
#   3. deletes  data/out/screening_log.csv
#   4. empties  data/out/calibration        (regenerate: scripts/calibrate.py)
#   5. empties  data/uipath/<Decision>      (keeping the folders themselves)
#   6. deletes  data/uipath/Screening_Report.xlsx
#
# What it never touches: data/resumes, data/jds, config/, or anything the five
# scoring modules read. Those are inputs, not demo state.
#
# Why the real work is Python and reset_demo.ps1 is only a wrapper: on this
# machine any Windows PowerShell 5.1 file operation on the deliberately
# malformed demo resume terminated the whole shell - exit code 0, no error
# record, no trapped exception - leaving the reset half done and the demo in a
# broken state. Python's shutil handles the same files without complaint.
# See PROGRESS.md Section D #16. All I/O still goes through core/storage.py.

import argparse
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.storage import (SCREENING_LOG_PATH, clear_dir, copy_file,  # noqa: E402
                          delete_file, list_files)

DECISION_FOLDERS = ("Shortlisted", "Review", "Rerouted", "Rejected", "Exceptions")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset the RPA demo to a known state.")
    parser.add_argument("--inbox", default="data/inbox")
    parser.add_argument("--seed", default="data/inbox_seed")
    parser.add_argument("--runs", default="data/out/runs")
    parser.add_argument("--calibration", default="data/out/calibration")
    parser.add_argument("--uipath", default="data/uipath")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change, change nothing")
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parents[1]
    prefix = "[dry run] " if args.dry_run else ""

    print()
    print("RADIX RPA demo reset")
    print(f"  root: {root}")
    if args.dry_run:
        print("  DRY RUN - nothing will be changed")
    print()

    # --- 1 - inbox, restored from the seed --------------------------------
    # Guard first: without a seed, clearing the inbox destroys the demo data.
    seed_files = list_files(args.seed)
    if not seed_files:
        print(f"  ERROR  {args.seed} is missing or empty - refusing to clear "
              f"{args.inbox}.")
        print("         Recreate the seed (4 sample resumes plus the unreadable "
              "file) and run this again.")
        return 1

    strays = [n for n in list_files(args.inbox) if n not in seed_files]
    if not args.dry_run:
        for name in strays:
            delete_file(str(pathlib.Path(args.inbox) / name))
        for name in seed_files:
            copy_file(str(pathlib.Path(args.seed) / name), args.inbox)
    print(f"  {prefix}inbox        restored {len(seed_files)} seed file(s), "
          f"removed {len(strays)} stray file(s)")

    # --- 2 to 4 - generated output ---------------------------------------
    for label, path in (("runs", args.runs), ("calibration", args.calibration)):
        n = len(list_files(path)) + sum(
            1 for p in pathlib.Path(path).iterdir() if p.is_dir()
        ) if pathlib.Path(path).is_dir() else 0
        if not args.dry_run:
            n = clear_dir(path)
        print(f"  {prefix}{label:<12} emptied {path} ({n} removed)")

    if pathlib.Path(SCREENING_LOG_PATH).is_file():
        if not args.dry_run:
            delete_file(SCREENING_LOG_PATH)
        print(f"  {prefix}log          deleted {SCREENING_LOG_PATH}")
    else:
        print("  log          already absent")

    # --- 5 and 6 - UiPath output ------------------------------------------
    for folder in DECISION_FOLDERS:
        path = pathlib.Path(args.uipath) / folder
        n = len(list_files(str(path)))
        if not args.dry_run:
            n = clear_dir(str(path))
        print(f"  {prefix}uipath       {folder:<12} {n} file(s) removed")

    report = pathlib.Path(args.uipath) / "Screening_Report.xlsx"
    if report.is_file():
        if not args.dry_run:
            delete_file(str(report))
        print(f"  {prefix}report       deleted {report.as_posix()}")
    else:
        print("  report       already absent")

    # --- proof, not a promise ---------------------------------------------
    final = list_files(args.inbox)
    print()
    print(f"  {args.inbox} now holds {len(final)} file(s):")
    for name in final:
        size = (pathlib.Path(args.inbox) / name).stat().st_size
        print(f"    {name:<26} {size:>8} bytes")

    if not args.dry_run and len(final) != len(seed_files):
        print()
        print(f"  ERROR  expected {len(seed_files)} file(s) in {args.inbox} "
              f"but found {len(final)}.")
        return 1

    leftover = sum(len(list_files(str(pathlib.Path(args.uipath) / f)))
                   for f in DECISION_FOLDERS)
    if not args.dry_run and leftover:
        print()
        print(f"  ERROR  {leftover} file(s) still sitting in {args.uipath}.")
        return 1

    print()
    print("Ready. Next: python scripts/run_inbox.py")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
