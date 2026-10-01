import json
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from src.llm_client import GeminiClient


def test_dashboard_submits_notice_and_renders_extracted_action(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    reply = {
        "title": "Scholarship applications",
        "category": "scholarship",
        "issued_by": "Student Affairs",
        "summary": "Eligible students should submit an application.",
        "actions": [
            {
                "task": "Submit the scholarship application",
                "deadline": "2026-10-12",
                "priority": "high",
                "applies_to": "Students with CGPA 8.5+",
                "required_documents": ["Marksheet", "Income certificate"],
                "fee": None,
                "where_or_contact": "Scholarship portal",
                "confidence": 0.94,
            },
            {
                "task": "Attend the scholarship briefing",
                "event_date": "2026-10-14",
                "event_date_text": "14 October",
                "time": "10:30 AM",
                "priority": "medium",
                "applies_to": "Eligible students",
            },
        ],
        "ambiguities": [],
    }
    monkeypatch.setattr(GeminiClient, "complete", lambda self, system, messages: json.dumps(reply))

    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10).run()
    assert not app.exception
    assert any("AI Mode • Gemini" in item.value for item in app.markdown)

    app.text_area(key="notice_text").set_value("Scholarship applications close on 12 October.")
    app.button(key="extract_notice").click().run()

    assert not app.exception
    assert any("Submit the scholarship application" in item.value for item in app.markdown)
    assert app.metric[0].value == "2"
    assert app.metric[1].value == "1"
    assert any("Event date / time" in item.value for item in app.markdown)
    assert any("10:30 AM" in item.value for item in app.markdown)


def test_dashboard_uses_demo_mode_without_an_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10).run()
    assert not app.exception
    assert any("Demo Mode • Local extraction" in item.value for item in app.markdown)
    assert any("GEMINI_API_KEY is not configured" in item.value for item in app.markdown)
    app.segmented_control(key="input_mode").select("Upload .txt").run()
    assert app.get("file_uploader")
    app.segmented_control(key="input_mode").select("Paste text").run()

    app.text_area(key="notice_text").set_value(
        "All students must submit the registration form by 12 October 2026."
    )
    app.button(key="extract_notice").click().run()

    assert not app.exception
    assert not app.error
    assert any("Submit the registration form" in item.value for item in app.markdown)
    assert app.metric[0].value == "1"


def test_dashboard_loads_and_clears_a_real_sample_notice(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10).run()
    assert not app.exception

    app.button(key="load-sample-0").click().run()
    assert not app.exception
    assert "End Semester Exam Form" in app.text_area(key="notice_text").value

    app.button(key="clear_notice").click().run()
    assert not app.exception
    assert app.text_area(key="notice_text").value == ""


def test_dashboard_uses_mocked_gemini_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = {
        "title": "Exam notice",
        "category": "exam",
        "summary": "Register and attend the exam.",
        "actions": [
            {"task": "Register for the exam", "deadline": "2026-10-05", "priority": "high"}
        ],
    }
    requests = []

    def fake_complete(self, system, messages):
        requests.append((system, messages))
        return json.dumps(response)

    monkeypatch.setattr(GeminiClient, "complete", fake_complete)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10).run()

    assert not app.exception
    assert any("AI Mode • Gemini" in item.value for item in app.markdown)
    app.text_area(key="notice_text").set_value("Students must register for the exam by 5 October 2026.")
    app.button(key="extract_notice").click().run()

    assert not app.exception
    assert len(requests) == 1
    assert "college notices" in requests[0][0]
    assert "by 5 October 2026" in requests[0][1][0]["content"]
    assert any("Register for the exam" in item.value for item in app.markdown)


def test_dashboard_falls_back_if_gemini_fails_during_generation(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fail_generation(self, system, messages):
        raise RuntimeError("Gemini request failed")

    monkeypatch.setattr(GeminiClient, "complete", fail_generation)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10).run()
    app.text_area(key="notice_text").set_value(
        "All students must submit the registration form by 12 October 2026."
    )
    app.button(key="extract_notice").click().run()

    assert not app.exception
    assert not app.error
    assert any("Demo Mode • Local extraction" in item.value for item in app.markdown)
    assert any("Demo Mode" in item.value for item in app.markdown)
    assert any("Submit the registration form" in item.value for item in app.markdown)