import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.contract import CATEGORY_CODES  # noqa: E402

COLUMN_TO_CODE = {
    "coding": "COD",
    "data_structures_and_algorithms": "DSA",
    "object_oriented_programming_and_design": "OOD",
    "aptitude_and_problem_solving": "APTI",
    "communication_skills": "COMM",
    "ai_native_engineering": "AI",
    "devops_and_cloud": "CLOUD",
    "sql_and_design": "SQL",
    "software_engineering": "SWE",
    "system_design_and_architecture": "SYSD",
    "computer_networking": "NETW",
    "operating_system": "OS",
}

SRC = pathlib.Path("data/skilll_levels_company.csv")
DST = pathlib.Path("data/talent_check_company_skillsets.json")


def main():
    with SRC.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [col for col in COLUMN_TO_CODE if col not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"CSV is missing expected columns: {missing}. "
                f"Found columns: {reader.fieldnames}"
            )

        out = {}
        for row in reader:
            name = (row.get("companies") or "").strip()
            if not name or name in out:  # dataset contains duplicate rows — keep first
                continue
            skillsets = {}
            for col, code in COLUMN_TO_CODE.items():
                raw = (row.get(col) or "").strip()
                if not raw:
                    continue
                level, _, band = raw.partition("-")
                skillsets[code] = {
                    "required_level": int(level),
                    "band": band or "NA",
                    "raw": raw,
                }
            out[name] = {"company": name, "skillsets": skillsets}

    assert all(code in CATEGORY_CODES for code in COLUMN_TO_CODE.values())

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} companies to {DST}")


if __name__ == "__main__":
    main()
