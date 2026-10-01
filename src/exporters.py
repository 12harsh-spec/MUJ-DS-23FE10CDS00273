"""Render results as a Markdown checklist and an .ics calendar file."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from .schema import NoticeResult

ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def to_markdown(r: NoticeResult) -> str:
    out = [f"# {r.title}", f"*{r.category}*" + (f" · {r.issued_by}" if r.issued_by else ""),
           "", r.summary, "", "## To do"]
    for a in r.actions:
        dates = [f"due {a.deadline:%a %d %b %Y}" if a.deadline else "no fixed deadline"]
        if a.event_date:
            event = f"event {a.event_date:%a %d %b %Y}"
            if a.time:
                event += f" at {a.time}"
            dates.append(event)
        elif a.time:
            dates.append(f"time {a.time}")
        line = f"- [ ] {ICON[a.priority]} **{a.task}** ({'; '.join(dates)}; {a.applies_to})"
        extras = []
        if a.fee:
            extras.append(f"fee: {a.fee}")
        if a.required_documents:
            extras.append("bring: " + ", ".join(a.required_documents))
        if a.where_or_contact:
            extras.append(f"where: {a.where_or_contact}")
        if a.confidence < 0.6:
            extras.append("⚠ low confidence, verify")
        out.append(line + (" — " + "; ".join(extras) if extras else ""))
    if r.ambiguities:
        out += ["", "## Check these"] + [f"- {x}" for x in r.ambiguities]
    return "\n".join(out) + "\n"


def _esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def to_ics(results: list[NoticeResult]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NoticeActionExtractor//EN"]
    for r in results:
        for a in r.actions:
            for event_type, event_date in (("deadline", a.deadline), ("event", a.event_date)):
                if not event_date:
                    continue
                uid = hashlib.md5(
                    f"{r.title}|{a.task}|{event_type}|{event_date}".encode()
                ).hexdigest()
                desc = f"{r.title}. {event_type.title()} date: {event_date:%Y-%m-%d}. Applies to: {a.applies_to}."
                if a.time and event_type == "event":
                    desc += f" Time: {a.time}."
                if a.fee:
                    desc += f" Fee: {a.fee}."
                lines += [
                    "BEGIN:VEVENT", f"UID:{uid}@notice-actions", f"DTSTAMP:{stamp}",
                    f"DTSTART;VALUE=DATE:{event_date:%Y%m%d}",
                    f"DTEND;VALUE=DATE:{event_date + timedelta(days=1):%Y%m%d}",
                    f"SUMMARY:{_esc(a.task)}", f"DESCRIPTION:{_esc(desc)}", "END:VEVENT",
                ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
