# The ONLY file that touches disk. Every module output is saved here.

import csv
import json
import pathlib
import re
import shutil
import time

DATA_OUT = "data/out"
COMPANY_DATA_PATH = "data/talent_check_company_skillsets.json"
CODING_CACHE_DIR = "data/cache"
SCREENING_CONFIG_PATH = "config/screening.json"
JD_COMPANIES_PATH = "config/jd_companies.json"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# R1 — the audit log every agent run appends one row to.
SCREENING_LOG_PATH = "data/out/screening_log.csv"
SCREENING_LOG_COLUMNS = [
    "timestamp", "resume_file", "candidate_name", "email", "company", "role",
    "readiness", "verdict", "match", "decision", "reason",
    "rerouted_to_role", "rerouted_to_company", "rerouted_score",
    "top_gaps", "missing_skills", "feedback_file", "stages_ok", "error",
]


def rel_path(path) -> str:
    """Repo-root-relative with forward slashes, so a path survives being pasted
    into UiPath, a CSV cell or JSON. Falls back to an absolute POSIX path for
    anything outside the repo (e.g. a pytest tmp_path)."""
    p = pathlib.Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def save_json(name: str, payload: dict, out_dir: str | None = None) -> str:
    target = pathlib.Path(out_dir if out_dir is not None else DATA_OUT)
    target.mkdir(parents=True, exist_ok=True)
    path = target / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return rel_path(path)


def load_json(name: str, out_dir: str | None = None) -> dict | None:
    path = pathlib.Path(out_dir if out_dir is not None else DATA_OUT) / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_text(path: str, text: str) -> str:
    """Write a text artefact (feedback.md, a report) to an explicit path."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return rel_path(target)


def append_log_row(row: dict, log_path: str | None = None) -> str:
    """Append one audit row to screening_log.csv, writing the header once.

    Columns are fixed (SCREENING_LOG_COLUMNS) so the CSV shape is stable for
    UiPath's Read CSV. Unknown keys are dropped, missing keys become "".
    No clock is read here — the caller supplies "timestamp" if it wants one.
    """
    path = pathlib.Path(log_path if log_path is not None else SCREENING_LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    # UTF-8 *with* BOM, written once with the header: Excel, PowerShell 5.1 and
    # UiPath's Read CSV all fall back to the ANSI codepage without it, which
    # turns the em-dash in a reason into "â€”". Appends stay plain utf-8 so the
    # BOM is never written a second time mid-file.
    encoding = "utf-8-sig" if needs_header else "utf-8"
    with path.open("a", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(
            f, fieldnames=SCREENING_LOG_COLUMNS, extrasaction="ignore", restval=""
        )
        if needs_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in SCREENING_LOG_COLUMNS})
    return rel_path(path)


def load_company_data() -> dict:
    path = pathlib.Path(COMPANY_DATA_PATH)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


DELETE_ATTEMPTS = 5
DELETE_BACKOFF_SECONDS = 0.1


def _remove_with_retry(target: pathlib.Path) -> None:
    """Delete a file or tree, retrying a few times on a sharing violation.

    On Windows a file written moments ago can still be held by a virus scanner
    or an indexer, and the unlink raises PermissionError. Observed on the
    deliberately malformed demo resume right after the bot moved it into
    Exceptions, which left the reset incomplete. Retries are purely about
    timing - they cannot change any result - so determinism is unaffected.
    """
    last = None
    for attempt in range(DELETE_ATTEMPTS):
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return
        except (PermissionError, OSError) as e:
            last = e
            if attempt < DELETE_ATTEMPTS - 1:
                time.sleep(DELETE_BACKOFF_SECONDS * (attempt + 1))
    raise last


def delete_file(path: str) -> bool:
    """Delete one file if it is there. Returns whether anything was removed."""
    p = pathlib.Path(path)
    if not p.is_file():
        return False
    _remove_with_retry(p)
    return True


def clear_dir(path: str, keep: tuple[str, ...] = (".gitkeep",)) -> int:
    """Empty a directory, creating it if absent. Returns how many entries went.

    `keep` names files to leave in place, so an intentionally-empty folder keeps
    its placeholder and does not disappear.
    """
    target = pathlib.Path(path)
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
        return 0
    removed = 0
    for entry in sorted(target.iterdir(), key=lambda p: p.name):
        if entry.name in keep:
            continue
        _remove_with_retry(entry)
        removed += 1
    return removed


def copy_file(src: str, dest_dir: str) -> str:
    """Copy one file into dest_dir, overwriting in place.

    Overwrite rather than delete-then-copy on purpose: on Windows a delete can
    stay pending while another process still holds a handle, and a file written
    back under the same name is then removed when that pending delete lands.
    """
    source = pathlib.Path(src)
    target_dir = pathlib.Path(dest_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copyfile(str(source), str(target))
    return rel_path(target)


def list_files(path: str, keep_out: tuple[str, ...] = (".gitkeep",)) -> list[str]:
    """File names directly inside a directory, sorted. [] if it does not exist."""
    target = pathlib.Path(path)
    if not target.is_dir():
        return []
    return sorted(p.name for p in target.iterdir()
                  if p.is_file() and p.name not in keep_out)


def move_file(src: str, dest_dir: str) -> str:
    """Move one file into dest_dir, replacing any file already there.

    The bot's file moves go through the one I/O gate too (rule 4). Returns the
    new location, repo-relative with forward slashes.
    """
    source = pathlib.Path(src)
    target_dir = pathlib.Path(dest_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        target.unlink()
    shutil.move(str(source), str(target))
    return rel_path(target)


def _load_config(path: str) -> dict:
    """Config reads go through the one I/O gate too. Missing or malformed file
    returns {} — never raises, so the caller falls back to its own defaults."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def load_screening_config() -> dict:
    """R3 — agent thresholds from config/screening.json."""
    return _load_config(SCREENING_CONFIG_PATH)


def load_jd_companies() -> dict:
    """R4 — {jd filename stem: company name} overrides for company auto-detection."""
    return _load_config(JD_COMPANIES_PATH)


def _coding_cache_path(platform: str, username: str) -> pathlib.Path:
    safe_user = re.sub(r"[^a-zA-Z0-9_.-]", "_", username.strip())
    return pathlib.Path(CODING_CACHE_DIR) / f"coding_{platform}_{safe_user}.json"


def save_coding_cache(platform: str, username: str, stats: dict) -> str:
    """F1.4 — cache every successful coding-profile fetch so re-runs and demos
    are reproducible without a network call."""
    path = _coding_cache_path(platform, username)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return str(path)


def load_coding_cache(platform: str, username: str) -> dict | None:
    path = _coding_cache_path(platform, username)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
