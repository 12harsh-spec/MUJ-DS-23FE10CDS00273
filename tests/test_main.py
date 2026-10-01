from pathlib import Path

import yaml

from src.main import main
from src.llm_client import GeminiClient


def test_cli_uses_demo_when_gemini_key_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "outputs")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    notice_path = tmp_path / "registration.txt"
    notice_path.write_text(
        "All students must submit the registration form by 12 October 2026.",
        encoding="utf-8",
    )

    result = main([
        str(notice_path),
        "--config",
        str(config_path),
        "--today",
        "2026-10-01",
    ])

    assert result == 0
    assert "GEMINI_API_KEY is unavailable" in capsys.readouterr().err
    exported = (tmp_path / "outputs" / "registration.md").read_text(encoding="utf-8")
    assert "Submit the registration form" in exported


def test_cli_falls_back_after_gemini_request_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        GeminiClient,
        "complete",
        lambda self, system, messages: (_ for _ in ()).throw(RuntimeError("Gemini request failed")),
    )
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "outputs")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    notice_path = tmp_path / "registration.txt"
    notice_path.write_text(
        "All students must submit the registration form by 12 October 2026.",
        encoding="utf-8",
    )

    result = main([str(notice_path), "--config", str(config_path), "--today", "2026-10-01"])

    assert result == 0
    assert "Gemini request failed" in capsys.readouterr().err
    exported = (tmp_path / "outputs" / "registration.md").read_text(encoding="utf-8")
    assert "Submit the registration form" in exported