"""Google Gemini client used by the notice extraction pipeline."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from google import genai
from google.genai import types


class GeminiClient:
    def __init__(self, cfg: dict):
        self.cfg = cfg["llm"]
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        self.model = self.cfg["model"]
        self.client = genai.Client(api_key=api_key)
        self.cache_dir = Path(self.cfg.get("cache_dir", ".cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, system: str, messages: list[dict]) -> Path:
        blob = json.dumps(
            [self.model, self.cfg.get("temperature", 0.0), system, messages],
            sort_keys=True,
        )
        return self.cache_dir / (hashlib.sha256(blob.encode()).hexdigest() + ".txt")

    def complete(self, system: str, messages: list[dict]) -> str:
        cache_file = self._key(system, messages)
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8")

        contents = []
        for message in messages:
            role = "model" if message.get("role") == "assistant" else message.get("role")
            if role not in {"user", "model"}:
                continue
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=message["content"])],
                )
            )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=self.cfg.get("temperature", 0.0),
                    max_output_tokens=self.cfg.get("max_tokens", 1500),
                    response_mime_type="application/json",
                ),
            )
            text = response.text
        except Exception:
            raise RuntimeError(
                "Gemini request failed. Check your API key, connection, quota, and try again."
            ) from None

        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Gemini returned no text. Try the notice again.")
        cache_file.write_text(text, encoding="utf-8")
        return text

    def close(self) -> None:
        self.client.close()


def create_llm_client(cfg: dict) -> GeminiClient:
    provider = cfg.get("llm", {}).get("provider", "gemini").lower()
    if provider == "gemini":
        return GeminiClient(cfg)
    raise ValueError(f"Unsupported LLM provider: {provider}")
