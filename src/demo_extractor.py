"""Deterministic, offline extraction for the dashboard's no-key demo mode."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .schema import Action, NoticeResult

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE = re.compile(
    rf"\b(?P<date>(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|"
    rf"\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}(?:\s+\d{{4}})?|"
    rf"{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?(?:\s+\d{{4}})?))\b",
    re.IGNORECASE,
)
_WEEKDAY = re.compile(
    r"\b(?P<phrase>(?:next|this)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\b",
    re.IGNORECASE,
)
_TIME = re.compile(
    r"\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)"
    r"(?:\s*(?:to|[-–])\s*(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?))?\b",
    re.IGNORECASE,
)
_RELATIVE = re.compile(
    r"\b(?P<phrase>within\s+(?:\d+|a|one|two|three|four|five|six|seven)\s+(?:days?|weeks?))\b",
    re.IGNORECASE,
)
_ACTION_VERB = re.compile(
    r"\b(?P<verb>submit(?:ted|ting)?|register|apply|upload|pay|paid|contact|attend|complete|fill|"
    r"report|bring|collect|visit|email|send|deposit|appear|download|renew|enrol|"
    r"enroll|confirm|provide|return|participate|check|sign|clear|purchase|book|"
    r"prepare|carry|present|reach|join|respond|inform|obtain|write|sit)\b",
    re.IGNORECASE,
)
_DIRECTIVE = re.compile(
    r"\b(?:must|should|need to|are required to|is required to|are requested to|"
    r"is requested to|are advised to|is advised to|required)\b",
    re.IGNORECASE,
)
_DEADLINE_CUE = re.compile(r"\b(?:last date|deadline|due date|due by|closes? on|by)\b", re.IGNORECASE)
_DEADLINE_CONTEXT = re.compile(r"\b(?:last date|deadline|due date|due by)\b", re.IGNORECASE)
_EVENT = re.compile(
    r"\b(?:exam(?:ination)?|interview|orientation|workshop|seminar|event|meeting|"
    r"counselling|counseling|reporting|induction|fest|webinar)\b",
    re.IGNORECASE,
)
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_NUMBER_WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
_DOCUMENTS = re.compile(
    r"\b(?:identity card|id card|marksheet|mark sheet|income certificate|bank passbook(?: copy)?|"
    r"medical certificate|admit card|application form|passport[- ]size photo(?:graph)?|"
    r"photograph|fee receipt|bonafide certificate|domicile certificate|caste certificate|"
    r"signature|resume|cv)\b",
    re.IGNORECASE,
)
_FEE = re.compile(r"\b(?:Rs\.?|INR)\s*[\d,]+(?:\.\d{1,2})?|₹\s*[\d,]+(?:\.\d{1,2})?", re.IGNORECASE)
_EMAIL_OR_URL = re.compile(r"(?:[\w.+-]+@[\w.-]+\.\w+|https?://\S+|www\.\S+)", re.IGNORECASE)


def _sentences(notice: str) -> list[str]:
    notice = re.sub(r"(?m)^\s*(?:[-•*]|\d+[.)])\s+", "; ", notice)
    notice = re.sub(r"\s*\n+\s*", " ", notice)
    return [part.strip(" \t\r\n-•") for part in re.split(r"(?<=[.!?])\s+|[;]+", notice) if part.strip(" \t\r\n-•")]


def _parse_explicit_date(value: str, reference_date: date) -> date | None:
    cleaned = re.sub(r"(\d)(st|nd|rd|th)", r"\1", value, flags=re.IGNORECASE).replace(",", "")
    formats = (
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
        "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y",
    )
    for candidate in (cleaned, f"{cleaned} {reference_date.year}"):
        for date_format in formats:
            try:
                return datetime.strptime(candidate, date_format).date()
            except ValueError:
                continue
    return None


def _find_deadline(text: str, reference_date: date) -> tuple[date | None, str | None]:
    explicit = _DATE.search(text)
    if explicit:
        parsed = _parse_explicit_date(explicit.group("date"), reference_date)
        if parsed:
            return parsed, explicit.group("date")

    weekday = _WEEKDAY.search(text)
    if weekday:
        target = _WEEKDAYS.index(weekday.group(0).split()[-1].lower())
        offset = (target - reference_date.weekday()) % 7
        if weekday.group(0).lower().startswith("next") or offset == 0:
            offset += 7
        return reference_date + timedelta(days=offset), weekday.group("phrase")

    relative = _RELATIVE.search(text)
    if relative:
        phrase = relative.group("phrase")
        amount = re.search(r"\d+|a|one|two|three|four|five|six|seven", phrase, re.IGNORECASE).group(0).lower()
        count = int(amount) if amount.isdigit() else _NUMBER_WORDS[amount]
        if "week" in phrase.lower():
            count *= 7
        return reference_date + timedelta(days=count), phrase
    return None, None


def _category(text: str) -> str:
    value = text.lower()
    for category, words in (
        ("scholarship", ("scholarship", "financial aid", "stipend")),
        ("exam", ("exam", "examination", "admit card", "hall ticket")),
        ("placement", ("placement", "interview", "recruitment", "job drive")),
        ("fee_payment", ("fee", "payment", "tuition", "deposit")),
        ("registration", ("registration", "register", "enrol", "enroll")),
        ("event", ("event", "seminar", "workshop", "orientation", "webinar", "fest")),
        ("holiday", ("holiday", "vacation", "campus closed")),
        ("submission", ("submit", "submission", "upload", "application")),
    ):
        if any(word in value for word in words):
            return category
    return "general"


def _task(sentence: str, verb_match: re.Match[str] | None) -> str:
    lower = sentence.lower()
    if verb_match is None:
        if "registr" in lower:
            return "Complete the registration"
        if "application" in lower:
            return "Submit the application"
        if "fee" in lower or "payment" in lower:
            return "Pay the required fee"
        return "Complete the required action"
    text = sentence[verb_match.start("verb"):].strip(" :,-")
    text = re.sub(r"\s+", " ", text).rstrip(" .")
    text = re.sub(r"^submitted\b", "Submit", text, flags=re.IGNORECASE)
    text = re.sub(r"^paid\b", "Pay", text, flags=re.IGNORECASE)
    for date_match in (_DATE.search(text), _WEEKDAY.search(text), _RELATIVE.search(text)):
        if date_match:
            connector = re.search(r"\b(?:by|before|within|on)\s*$", text[:date_match.start()], re.IGNORECASE)
            if connector:
                text = text[:connector.start()].rstrip(" ,;:")
                break
    if len(text) > 115:
        text = text[:112].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return text[:1].upper() + text[1:]


def _applies_to(sentence: str, verb_match: re.Match[str] | None) -> str:
    if verb_match is None:
        return "Students mentioned in the notice"
    prefix = sentence[:verb_match.start("verb")]
    groups = re.findall(
        r"\b((?:(?:all|eligible|final[- ]year|first[- ]year|second[- ]year|third[- ]year|"
        r"fourth[- ]year|\d+(?:st|nd|rd|th))\s+){0,3}(?:[\w./&-]+\s+){0,3}students?)\b",
        prefix,
        re.IGNORECASE,
    )
    if groups:
        return re.sub(r"\s+", " ", groups[-1]).strip().capitalize()
    return "Students mentioned in the notice"


def _documents(text: str) -> list[str]:
    found: list[str] = []
    for match in _DOCUMENTS.finditer(text):
        value = match.group(0).title()
        if value not in found:
            found.append(value)
    return found


def _where_or_contact(text: str) -> str | None:
    contact = _EMAIL_OR_URL.search(text)
    if contact:
        return contact.group(0).rstrip(".,)")
    location = re.search(
        r"\b(?:at|to(?!\s+be\b)|via|through)\s+(?:the\s+)?([^,.;]+(?:office|portal|counter|department|ERP|HOD|accounts))\b",
        text,
        re.IGNORECASE,
    )
    return location.group(1).strip() if location else None


def _priority(
    sentence: str,
    deadline_text: str | None,
    is_event: bool,
    reference_date: date,
    deadline: date | None,
) -> str:
    if re.search(r"\b(?:urgent|immediately|penalt\w*|late fee|disqualif\w*|forfeit\w*)\b", sentence, re.IGNORECASE):
        return "high"
    if deadline and deadline <= reference_date + timedelta(days=3) and not is_event:
        return "high"
    if deadline_text and _DEADLINE_CUE.search(sentence) and not is_event:
        return "medium"
    if _DIRECTIVE.search(sentence) or re.search(
        r"\b(?:mandatory|should|important|recommended|requested|to be submitted)\b",
        sentence,
        re.IGNORECASE,
    ):
        return "medium"
    if re.match(
        r"\s*(?:submit|register|apply|upload|pay|attend|complete|fill|report|bring|collect|"
        r"visit|send|deposit|confirm|provide|return|participate|sign|clear|purchase|book|"
        r"prepare|carry|write)\b",
        sentence,
        re.IGNORECASE,
    ):
        return "medium"
    return "low"


def extract_demo(notice: str, reference_date: date) -> NoticeResult:
    """Extract likely actions and dates using local rules only; makes no network calls."""
    notice = notice.strip()
    if not notice:
        raise ValueError("Notice is empty")

    sentences = _sentences(notice)
    category = _category(notice)
    candidates: list[tuple[int, str, re.Match[str] | None, bool]] = []
    for index, sentence in enumerate(sentences):
        verb_match = _ACTION_VERB.search(sentence)
        deadline_only = bool(_DEADLINE_CUE.search(sentence) and _DATE.search(sentence))
        event_match = bool(_EVENT.search(sentence) and _find_deadline(sentence, reference_date)[0])
        if verb_match:
            candidates.append((index, sentence, verb_match, False))
        elif event_match:
            candidates.append((index, sentence, None, True))
        elif deadline_only and re.search(r"\b(?:registr\w*|application|fee|payment|submission)\b", sentence, re.IGNORECASE):
            candidates.append((index, sentence, None, False))

    actions: list[Action] = []
    ambiguities: list[str] = []
    for index, sentence, verb_match, is_event in candidates:
        event_term = _EVENT.search(sentence)
        attends_event = bool(
            event_term
            and verb_match
            and verb_match.group("verb").lower() in {"attend", "report", "appear", "sit", "join"}
        )
        is_event_action = is_event or attends_event
        if is_event_action:
            event_name = event_term.group(0).lower() if event_term else "event"
            task = "Report at the stated time and location" if event_name == "reporting" else f"Attend the {event_name}"
        else:
            task = _task(sentence, verb_match)
        applies_to = _applies_to(sentence, verb_match)
        action_date, action_date_text = _find_deadline(sentence, reference_date)
        deadline = None if is_event_action else action_date
        deadline_text = None if is_event_action else action_date_text
        event_date = action_date if is_event_action else None
        event_date_text = action_date_text if is_event_action else None
        can_inherit_deadline = verb_match is not None and verb_match.group("verb").lower() not in {"contact", "email", "inform"}
        if deadline is None and not is_event_action and can_inherit_deadline:
            nearby = [
                (abs(other_index - index), other_sentence)
                for other_index, other_sentence in enumerate(sentences)
                if other_index != index and abs(other_index - index) <= 2
                and _DEADLINE_CONTEXT.search(other_sentence)
            ]
            if nearby:
                _, date_context = min(nearby, key=lambda item: item[0])
                deadline, deadline_text = _find_deadline(date_context, reference_date)

        fee_match = _FEE.search(sentence)
        actions.append(
            Action(
                task=task,
                description=sentence,
                deadline=deadline,
                deadline_text=deadline_text,
                event_date=event_date,
                event_date_text=event_date_text,
                time=(time_match.group(0) if (time_match := _TIME.search(sentence)) else None),
                priority=_priority(sentence, deadline_text, is_event_action, reference_date, deadline),
                applies_to=applies_to,
                required_documents=_documents(sentence),
                fee=fee_match.group(0) if fee_match else None,
                where_or_contact=_where_or_contact(sentence),
                confidence=0.76 if verb_match else 0.66,
            )
        )
        if deadline is None:
            ambiguities.append(f"No clear deadline was found for: {task}")

    actions.sort(key=lambda action: (action.deadline is None, action.deadline or date.max))
    first_line = next((line.strip() for line in notice.splitlines() if line.strip()), "College notice")
    first_line = re.split(r"(?<=[.!?])\s+", first_line, maxsplit=1)[0]
    title = re.sub(r"^(?:subject|title)\s*:\s*", "", first_line, flags=re.IGNORECASE)[:120]
    issuer_match = re.search(r"\b(?:issued by|from|contact)\s*:?\s*([^\n.;]+)", notice, re.IGNORECASE)
    issued_by = issuer_match.group(1).strip() if issuer_match else None

    if actions:
        due_count = sum(action.deadline is not None for action in actions)
        summary = f"The local demo found {len(actions)} likely action item(s) and {due_count} date(s) in this notice. Review the source details before acting."
    else:
        summary = "The local demo could not identify a clear action. Try including the complete notice text."

    return NoticeResult(
        title=title,
        category=category,
        issued_by=issued_by,
        summary=summary,
        actions=actions,
        ambiguities=ambiguities,
    )