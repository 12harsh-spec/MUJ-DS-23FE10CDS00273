"""CLI: python -m src.main samples/ [--today 2026-09-29] [--config config.yaml]"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .exporters import to_ics, to_markdown
from .demo_extractor import extract_demo
from .extractor import extract
from .llm_client import create_llm_client


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extract student actions from college notices")
    ap.add_argument("input", help="a .txt notice file or a folder of them")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today(),
                    help="reference date for relative deadlines (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    load_dotenv()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    prompts = yaml.safe_load(Path(cfg["prompts_file"]).read_text(encoding="utf-8"))
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    src = Path(args.input)
    files = sorted(src.glob("*.txt")) if src.is_dir() else [src]
    if not files:
        print("No .txt notices found.", file=sys.stderr)
        return 1

    provider = cfg["llm"].get("provider", "gemini").lower()
    llm = None
    if provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
        llm = create_llm_client(cfg)
        llm_available = True
    else:
        llm_available = False

    results = []
    for f in files:
        try:
            notice = f.read_text(encoding="utf-8")
            if not llm_available:
                print("[demo] GEMINI_API_KEY is unavailable; using deterministic local extraction.", file=sys.stderr)
                res = extract_demo(notice, args.today)
            else:
                try:
                    res = extract(notice, llm, prompts, args.today,
                                  cfg["max_notice_chars"], cfg["max_repairs"])
                except RuntimeError:
                    print("[demo] Gemini request failed; using deterministic local extraction.", file=sys.stderr)
                    res = extract_demo(notice, args.today)
        except Exception as err:  # keep going in batch mode
            print(f"[skip] {f.name}: {err}", file=sys.stderr)
            continue
        results.append(res)
        (out_dir / f"{f.stem}.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
        md = to_markdown(res)
        (out_dir / f"{f.stem}.md").write_text(md, encoding="utf-8")
        print(md)

    if results:
        (out_dir / "deadlines.ics").write_text(to_ics(results), encoding="utf-8")
        print(f"Saved {len(results)} notice(s) and deadlines.ics to {out_dir}/")
    if llm is not None:
        llm.close()
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
