"""Parse .eml files for dates/times using an LLM and output CSV."""

import csv
import email
import json
import os
from html.parser import HTMLParser
from io import StringIO


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

LLM_PROMPT = """\
You are given the plain-text body of a school bulletin email.
Extract every event that has a date and/or time mentioned.

Rules:
- Infer the year from context (the bulletin date in the subject or body tells you the year).
- If a date range is given (e.g. "Feb 16-20"), expand it into one row per day.
- Return ONLY a JSON array of objects. No other text.
- Each object must have exactly these keys:
  - "date": string in YYYY-MM-DD format
  - "time": string in HH:MM or HH:MM-HH:MM (24-hour) format, or "" if no specific time
  - "description": short description of the event
  - "is_deadline": boolean — set to true if the event is a deadline, due date, registration closing, or similar time-sensitive cutoff; false otherwise

Example output:
[
  {"date": "2026-02-10", "time": "12:00-13:00", "description": "ParentEd Talks", "is_deadline": false},
  {"date": "2026-02-12", "time": "", "description": "Auction Donations Due", "is_deadline": true}
]

Here is the email text:

"""


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract plain text."""

    def __init__(self):
        super().__init__()
        self._pieces = []

    def handle_data(self, data):
        self._pieces.append(data)

    def get_text(self):
        return "".join(self._pieces)


def _html_to_text(html):
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def parse_eml(file_path):
    """Read an .eml file and return the body as plain text.

    Prefers the text/html part (stripped to plain text), falls back to text/plain.
    """
    with open(file_path, "rb") as f:
        msg = email.message_from_bytes(f.read())

    html_body = None
    text_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html" and html_body is None:
                html_body = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
            elif content_type == "text/plain" and text_body is None:
                text_body = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", errors="replace"
        )
        if content_type == "text/html":
            html_body = payload
        else:
            text_body = payload

    if html_body:
        return _html_to_text(html_body)
    if text_body:
        return text_body
    return ""


def _load_llm_config(config_path=CONFIG_PATH):
    with open(config_path) as f:
        config = json.load(f)
    for key in ("llm_provider", "llm_model", "llm_api_key"):
        if key not in config:
            raise ValueError(f"Missing '{key}' in config.json")
    return config


def _call_anthropic(text, config):
    import anthropic

    client = anthropic.Anthropic(api_key=config["llm_api_key"])
    message = client.messages.create(
        model=config["llm_model"],
        max_tokens=4096,
        messages=[{"role": "user", "content": LLM_PROMPT + text}],
    )
    return message.content[0].text


def _call_openai(text, config):
    import openai

    client = openai.OpenAI(api_key=config["llm_api_key"])
    response = client.chat.completions.create(
        model=config["llm_model"],
        messages=[{"role": "user", "content": LLM_PROMPT + text}],
    )
    return response.choices[0].message.content


def extract_events_with_llm(text, config_path=CONFIG_PATH):
    """Send email text to the configured LLM and return a list of event dicts.

    Each dict has keys: date, time, description.
    """
    config = _load_llm_config(config_path)
    provider = config["llm_provider"]

    if provider == "anthropic":
        raw = _call_anthropic(text, config)
    elif provider == "openai":
        raw = _call_openai(text, config)
    else:
        raise ValueError(f"Unsupported llm_provider: {provider}")

    # Strip markdown code fences if the LLM wrapped its response
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]  # remove opening ```json line
        raw = raw.rsplit("```", 1)[0]  # remove closing ```
        raw = raw.strip()

    events = json.loads(raw)
    return events


DEDUP_PROMPT = """\
You are given a new calendar event and a list of existing calendar events on the same date.
Determine whether the new event is a duplicate of any existing event.
Two events are duplicates if they refer to the same real-world event, even if the wording differs slightly.

New event:
{new_event}

Existing events:
{existing_events}

Respond with ONLY a JSON object: {{"is_duplicate": true}} or {{"is_duplicate": false}}
"""


def _call_llm(prompt, config):
    """Call the configured LLM with an arbitrary prompt string."""
    provider = config["llm_provider"]
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=config["llm_api_key"])
        message = client.messages.create(
            model=config["llm_model"],
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    elif provider == "openai":
        import openai

        client = openai.OpenAI(api_key=config["llm_api_key"])
        response = client.chat.completions.create(
            model=config["llm_model"],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    else:
        raise ValueError(f"Unsupported llm_provider: {provider}")


def is_duplicate_event(new_event, existing_events, config_path=CONFIG_PATH):
    """Check if a new event duplicates any existing calendar event using an LLM.

    Args:
        new_event: Dict with 'date', 'time', 'description' keys.
        existing_events: List of Google Calendar event dicts for that date.
        config_path: Path to config.json.

    Returns:
        True if the LLM determines the event is a duplicate.
    """
    if not existing_events:
        return False

    config = _load_llm_config(config_path)

    new_event_str = f"Date: {new_event['date']}, Time: {new_event['time'] or 'all day'}, Description: {new_event['description']}"

    existing_lines = []
    for evt in existing_events:
        title = evt.get("summary", "(no title)")
        start = evt["start"].get("dateTime", evt["start"].get("date", ""))
        end = evt["end"].get("dateTime", evt["end"].get("date", ""))
        existing_lines.append(f"- Title: {title}, Start: {start}, End: {end}")
    existing_str = "\n".join(existing_lines)

    prompt = DEDUP_PROMPT.format(new_event=new_event_str, existing_events=existing_str)
    raw = _call_llm(prompt, config)

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

    result = json.loads(raw)
    return result.get("is_duplicate", False)


def to_csv(events, output_path):
    """Write a list of event dicts to a CSV file."""
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "time", "description", "is_deadline"])
        writer.writeheader()
        writer.writerows(events)
