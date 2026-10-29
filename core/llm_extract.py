# Optional LLM skill extraction. Same signature/shape as core.skill_dictionary.extract_skills.
# Never load-bearing: callers must wrap in try/except and fall back to the keyword extractor.

import json

from dotenv import load_dotenv

from core.contract import ALL_CODES, CATEGORY_NAMES, CONFIDENCE_LEVELS, validate_skill

load_dotenv()

MODEL = "claude-haiku-4-5"

_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "category_code": {"type": "string", "enum": ALL_CODES},
                    "evidence": {"type": "string"},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
                },
                "required": ["skill_name", "category_code", "evidence", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["skills"],
    "additionalProperties": False,
}

_CATEGORY_LIST = "\n".join(f"- {code}: {name}" for code, name in CATEGORY_NAMES.items())


def extract_skills(text: str, source_hint: str = "") -> list[dict]:
    import anthropic

    client = anthropic.Anthropic()

    prompt = (
        "Extract every distinct skill, technology, or competency mentioned in the "
        "document below. For each one, classify it into exactly one of these categories:\n"
        f"{_CATEGORY_LIST}\n\n"
        "Use OTHER only for named technologies that truly don't fit any category above.\n"
        "For each skill, give a short quote of the surrounding text as evidence, and rate "
        'confidence as "high", "medium", or "low" based on how central it is to the document.\n\n'
        f"Document{f' ({source_hint})' if source_hint else ''}:\n{text[:12000]}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )

    payload_text = next(block.text for block in response.content if block.type == "text")
    payload = json.loads(payload_text)

    skills = []
    for skill in payload.get("skills", []):
        try:
            validate_skill(skill)
        except ValueError:
            continue
        skills.append(skill)

    return skills
