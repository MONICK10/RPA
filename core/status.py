# Live tick system. A module is only "done" if its status entry says done
# AND its output file exists on disk AND that file passes its validator.

import datetime
import pathlib

from core.contract import validate_profile, validate_skill_list
from core.storage import DATA_OUT, load_json, save_json

STATUS_FILE = "status.json"

MODULES = {
    "m1_jd_analytics":    {"label": "JD Analytics",    "output": "jd_skills.json"},
    "m2_resume_parsing":  {"label": "Resume Parsing",  "output": "resume_skills.json"},
    "m3_profile_builder": {"label": "Profile Builder", "output": "profile.json"},
    "m4_talent_check":    {"label": "Talent Check",    "output": "talent_check_result.json"},
    "m5_skill_matching":  {"label": "Skill Matching",  "output": "skill_match_result.json"},
}

_RESULT_REQUIRED_KEYS = {
    "m4_talent_check": {"company", "readiness_score", "verdict", "skillset_gap", "top_gaps"},
    "m5_skill_matching": {
        "jd_source_file", "company", "role", "match_score",
        "matched_skills", "missing_skills", "category_coverage",
    },
}


def _passes_validator(module_key: str, payload: dict) -> bool:
    try:
        if module_key in ("m1_jd_analytics", "m2_resume_parsing"):
            validate_skill_list(payload)
            return True
        if module_key == "m3_profile_builder":
            validate_profile(payload)
            return True
        required = _RESULT_REQUIRED_KEYS.get(module_key)
        if required is not None:
            return required.issubset(payload.keys())
        return True
    except (ValueError, AttributeError):
        return False


def mark(module_key: str, ok: bool, detail: str = "") -> None:
    if module_key not in MODULES:
        raise ValueError(f"unknown module_key {module_key!r}")
    status = load_json(STATUS_FILE) or {}
    status[module_key] = {
        "label": MODULES[module_key]["label"],
        "state": "done" if ok else "failed",
        "detail": detail,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "output_file": f"{DATA_OUT}/{MODULES[module_key]['output']}",
    }
    save_json(STATUS_FILE, status)


def get_status() -> dict:
    recorded = load_json(STATUS_FILE) or {}
    result = {}
    for module_key, info in MODULES.items():
        entry = recorded.get(module_key)
        if entry is None:
            result[module_key] = {
                "label": info["label"],
                "state": "pending",
                "detail": "",
                "timestamp": "",
                "output_file": f"{DATA_OUT}/{info['output']}",
            }
            continue

        entry = dict(entry)
        if entry.get("state") == "done":
            payload = load_json(info["output"])
            if payload is None or not _passes_validator(module_key, payload):
                entry["state"] = "pending"
                entry["detail"] = ""
        result[module_key] = entry
    return result


def reset_status() -> None:
    save_json(STATUS_FILE, {})


def summary_line() -> str:
    status = get_status()
    done = sum(1 for entry in status.values() if entry["state"] == "done")
    return f"{done}/{len(MODULES)} modules complete"
