import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.extractor import extract
from src.llm_client import GeminiClient


CFG = {
    "llm": {
        "provider": "gemini",
        "model": "gemini-3.8-flash",
        "temperature": 0.0,
        "max_tokens": 800,
        "cache_dir": ".cache",
    }
}
PROMPTS = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "prompts" / "prompts.yaml").read_text(encoding="utf-8")
)
VALID_RESPONSE = {
    "title": "Exam notice",
    "category": "exam",
    "summary": "Register for the exam.",
    "actions": [
        {"task": "Register for the exam", "deadline": "2026-10-05", "priority": "high"}
    ],
}


class FakeGeminiModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result)


class FakeGeminiClient:
    def __init__(self, responses):
        self.models = FakeGeminiModels(responses)
        self.closed = False

    def close(self):
        self.closed = True


def test_gemini_client_uses_sdk_json_mode_and_existing_system_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake = FakeGeminiClient([json.dumps(VALID_RESPONSE)])
    monkeypatch.setattr("src.llm_client.genai.Client", lambda api_key: fake)
    cfg = {"llm": {**CFG["llm"], "cache_dir": str(tmp_path)}}

    result = GeminiClient(cfg).complete(
        PROMPTS["system"],
        [{"role": "user", "content": "Students must register by 5 October 2026."}],
    )

    request = fake.models.calls[0]
    assert json.loads(result)["title"] == "Exam notice"
    assert request["model"] == "gemini-3.8-flash"
    assert request["config"].system_instruction == PROMPTS["system"]
    assert request["config"].response_mime_type == "application/json"
    assert request["contents"][0].parts[0].text == "Students must register by 5 October 2026."


def test_gemini_repairs_malformed_response_before_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake = FakeGeminiClient(["not valid json", json.dumps(VALID_RESPONSE)])
    monkeypatch.setattr("src.llm_client.genai.Client", lambda api_key: fake)
    cfg = {"llm": {**CFG["llm"], "cache_dir": str(tmp_path)}}

    result = extract(
        "Students must register by 5 October 2026.",
        GeminiClient(cfg),
        PROMPTS,
        date(2026, 10, 1),
        max_repairs=1,
    )

    assert result.actions[0].deadline == date(2026, 10, 5)
    assert len(fake.models.calls) == 2
    assert [item.role for item in fake.models.calls[1]["contents"]] == ["user", "model", "user"]


def test_gemini_requires_key_without_exposing_one(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not configured"):
        GeminiClient(CFG)


def test_gemini_api_failure_is_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    fake = FakeGeminiClient([RuntimeError("request included test-secret-key")])
    monkeypatch.setattr("src.llm_client.genai.Client", lambda api_key: fake)
    cfg = {"llm": {**CFG["llm"], "cache_dir": str(tmp_path)}}

    with pytest.raises(RuntimeError, match="Gemini request failed") as error:
        GeminiClient(cfg).complete("System", [{"role": "user", "content": "Notice"}])

    assert "test-secret-key" not in str(error.value)