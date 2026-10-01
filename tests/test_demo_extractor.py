from datetime import date
from pathlib import Path

import pytest

from src.demo_extractor import extract_demo


def test_demo_extracts_actions_dates_priority_and_notice_details():
    notice = """Exam form registration
All 5th semester students must register for the exam by 12 October 2026.
Pay the examination fee of Rs 1,500 by 10 October 2026 through the ERP portal.
Bring your ID card and marksheet to the examination office.
"""

    result = extract_demo(notice, date(2026, 10, 1))

    assert result.category == "exam"
    assert len(result.actions) == 3
    assert result.actions[0].deadline == date(2026, 10, 10)
    assert result.actions[0].priority == "medium"
    assert result.actions[0].fee == "Rs 1,500"
    assert result.actions[1].deadline == date(2026, 10, 12)
    assert result.actions[1].applies_to == "All 5th semester students"
    assert result.actions[2].required_documents == ["Id Card", "Marksheet"]
    assert "examination office" in result.actions[0].where_or_contact.lower() or result.actions[2].where_or_contact
    assert result.actions[1].description


def test_demo_resolves_relative_deadline_and_event_date():
    notice = "Students should upload the application within one week. The orientation will be held on 12 October 2026."

    result = extract_demo(notice, date(2026, 10, 1))

    assert result.actions[0].deadline == date(2026, 10, 8)
    assert result.actions[0].priority == "medium"
    assert any(action.event_date == date(2026, 10, 12) for action in result.actions)


def test_demo_keeps_exam_date_and_time_separate_from_deadline():
    result = extract_demo(
        "Students must attend the final examination on 12 October 2026 at 9:00 AM.",
        date(2026, 10, 1),
    )

    exam = result.actions[0]
    assert exam.deadline is None
    assert exam.event_date == date(2026, 10, 12)
    assert exam.time == "9:00 AM"
    assert exam.priority == "medium"


def test_demo_returns_a_useful_empty_result_for_informational_notice():
    result = extract_demo("The library will remain open this week.", date(2026, 10, 1))

    assert result.actions == []
    assert "could not identify" in result.summary


def test_demo_handles_the_existing_scholarship_sample():
    notice = (Path(__file__).resolve().parents[1] / "samples" / "scholarship.txt").read_text(encoding="utf-8")

    result = extract_demo(notice, date(2026, 10, 1))

    upload = next(action for action in result.actions if action.task.startswith("Upload"))
    hard_copy = next(action for action in result.actions if action.task.startswith("Submit"))
    assert result.title == "Merit Scholarship 2026-27 applications are open."
    assert upload.applies_to == "Eligible students"
    assert upload.deadline == date(2026, 10, 12)
    assert upload.priority == "medium"
    assert "Bank Passbook Copy" in upload.required_documents
    assert hard_copy.deadline == date(2026, 10, 8)
    assert hard_copy.priority == "medium"
    contact = next(action for action in result.actions if action.task.startswith("Contact"))
    assert contact.deadline is None
    assert contact.priority == "low"


def test_demo_rejects_empty_notice():
    with pytest.raises(ValueError, match="Notice is empty"):
        extract_demo("  ", date(2026, 10, 1))