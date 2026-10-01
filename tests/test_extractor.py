import json
from datetime import date

import pytest
import yaml

from src.exporters import to_ics, to_markdown
from src.extractor import extract, parse_json
from src.schema import Action, NoticeResult

PROMPTS = yaml.safe_load(open("prompts/prompts.yaml", encoding="utf-8"))
GOOD = {
    "title": "Exam Form", "category": "exam", "summary": "Fill the form.",
    "actions": [
        {"task": "Pay fee", "deadline": "2026-10-09", "priority": "high",
         "applies_to": "5th sem", "fee": "Rs 1500", "confidence": 0.9},
        {"task": "Collect admit card", "deadline": None},
    ],
}


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, system, messages):
        self.calls += 1
        return self.replies.pop(0)


def test_parse_json_handles_fences():
    assert parse_json("```json\n{\"a\": 1}\n```") == {"a": 1}


def test_extract_sorts_and_validates():
    res = extract("notice", FakeLLM([json.dumps(GOOD)]), PROMPTS, date(2026, 9, 29))
    assert res.actions[0].deadline == date(2026, 10, 9)
    assert res.actions[-1].deadline is None


def test_extract_keeps_multiple_deadlines_separate_from_event_date_and_time():
    response = {
        "title": "Exam notice",
        "category": "exam",
        "summary": "Register, pay the fee, and attend the exam.",
        "actions": [
            {"task": "Register for exams", "deadline": "2026-10-05", "priority": "high"},
            {"task": "Pay the exam fee", "deadline": "2026-10-07", "priority": "medium"},
            {
                "task": "Attend the exam",
                "event_date": "2026-10-10",
                "event_date_text": "10 October",
                "time": "9:00 AM",
                "priority": "medium",
            },
        ],
    }

    result = extract("Register by 5 October and attend the exam on 10 October at 9:00 AM.",
                     FakeLLM([json.dumps(response)]), PROMPTS, date(2026, 10, 1))

    assert [action.deadline for action in result.actions[:2]] == [date(2026, 10, 5), date(2026, 10, 7)]
    assert result.actions[2].deadline is None
    assert result.actions[2].event_date == date(2026, 10, 10)
    assert result.actions[2].time == "9:00 AM"


def test_repair_loop_recovers():
    llm = FakeLLM(["not json at all", json.dumps(GOOD)])
    res = extract("notice", llm, PROMPTS, date(2026, 9, 29))
    assert llm.calls == 2 and res.title == "Exam Form"


def test_gives_up_after_repairs():
    with pytest.raises(ValueError):
        extract("notice", FakeLLM(["bad"] * 3), PROMPTS, date(2026, 9, 29))


def test_empty_notice_rejected():
    with pytest.raises(ValueError):
        extract("   ", FakeLLM([]), PROMPTS, date(2026, 9, 29))


def test_exporters():
    res = extract("notice", FakeLLM([json.dumps(GOOD)]), PROMPTS, date(2026, 9, 29))
    assert "- [ ]" in to_markdown(res)
    ics = to_ics([res])
    assert "DTSTART;VALUE=DATE:20261009" in ics and ics.count("BEGIN:VEVENT") == 1


def test_exporters_include_event_date_and_time():
    result = NoticeResult(
        title="Exam notice",
        category="exam",
        summary="Attend the exam.",
        actions=[
            Action(
                task="Attend the final exam",
                event_date=date(2026, 10, 10),
                time="9:00 AM",
                priority="medium",
            )
        ],
    )

    checklist = to_markdown(result)
    calendar = to_ics([result])
    assert "event Sat 10 Oct 2026 at 9:00 AM" in checklist
    assert "DTSTART;VALUE=DATE:20261010" in calendar
    assert "Time: 9:00 AM." in calendar
