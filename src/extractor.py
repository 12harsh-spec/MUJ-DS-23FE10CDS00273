"""Turns raw notice text into a validated NoticeResult using the LLM."""
from __future__ import annotations

import json
import re
from datetime import date

from pydantic import ValidationError

from .schema import NoticeResult


def parse_json(raw: str) -> dict:
    """Tolerate code fences or stray text around the JSON object."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in the reply")
    return json.loads(raw[start : end + 1])


def build_user_prompt(template: str, notice: str, today: date) -> str:
    return (
        template.replace("{{today}}", today.isoformat())
        .replace("{{weekday}}", today.strftime("%A"))
        .replace("{{notice}}", notice)
    )


def extract(notice: str, llm, prompts: dict, today: date,
            max_chars: int = 12000, max_repairs: int = 2) -> NoticeResult:
    notice = notice.strip()
    if not notice:
        raise ValueError("Notice is empty")
    notice = notice[:max_chars]

    messages = [{"role": "user",
                 "content": build_user_prompt(prompts["user"], notice, today)}]
    for attempt in range(max_repairs + 1):
        raw = llm.complete(prompts["system"], messages)
        try:
            result = NoticeResult.model_validate(parse_json(raw))
            result.actions.sort(key=lambda a: (a.deadline is None, a.deadline or date.max))
            return result
        except ValueError as err:  # covers JSONDecodeError and pydantic ValidationError
            if attempt == max_repairs:
                raise
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user",
                 "content": prompts["repair"].replace("{{error}}", str(err)[:800])},
            ]
