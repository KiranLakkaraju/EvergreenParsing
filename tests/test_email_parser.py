"""Unit tests for email_parser.py — all LLM calls are mocked."""

import csv
import os
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import patch, MagicMock

import pytest

from email_parser import parse_eml, extract_events_with_llm, is_duplicate_event, to_csv


# --- parse_eml tests ---

def _make_eml(html=None, text=None):
    """Create a temporary .eml file and return its path."""
    if html and text:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
    elif html:
        msg = MIMEText(html, "html")
    else:
        msg = MIMEText(text or "", "plain")
    msg["Subject"] = "Test Bulletin"
    msg["From"] = "test@example.com"

    fd, path = tempfile.mkstemp(suffix=".eml")
    with os.fdopen(fd, "wb") as f:
        f.write(msg.as_bytes())
    return path


def test_parse_eml_html_body():
    """HTML body is stripped to plain text."""
    path = _make_eml(html="<h1>Hello</h1><p>World</p>")
    try:
        result = parse_eml(path)
        assert "Hello" in result
        assert "World" in result
        assert "<h1>" not in result
    finally:
        os.unlink(path)


def test_parse_eml_plain_text():
    """Plain text body is returned as-is."""
    path = _make_eml(text="Hello World")
    try:
        result = parse_eml(path)
        assert "Hello World" in result
    finally:
        os.unlink(path)


def test_parse_eml_multipart_prefers_html():
    """When both HTML and plain text exist, HTML (stripped) is used."""
    path = _make_eml(html="<b>Rich</b> content", text="Plain content")
    try:
        result = parse_eml(path)
        assert "Rich" in result
        assert "<b>" not in result
    finally:
        os.unlink(path)


# --- extract_events_with_llm tests ---

FAKE_LLM_RESPONSE = '[{"date": "2026-02-10", "time": "12:00-13:00", "description": "ParentEd Talks", "is_deadline": false}]'

FAKE_CONFIG = {
    "calendar_id": "test",
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-5-20250929",
    "llm_api_key": "sk-test-key",
}


@patch("email_parser._call_anthropic", return_value=FAKE_LLM_RESPONSE)
@patch("email_parser._load_llm_config", return_value=FAKE_CONFIG)
def test_extract_events_anthropic(mock_config, mock_call):
    """Anthropic provider returns parsed events."""
    events = extract_events_with_llm("some email text")
    assert len(events) == 1
    assert events[0]["date"] == "2026-02-10"
    assert events[0]["time"] == "12:00-13:00"
    assert events[0]["description"] == "ParentEd Talks"


@patch("email_parser._call_openai", return_value=FAKE_LLM_RESPONSE)
@patch("email_parser._load_llm_config", return_value={**FAKE_CONFIG, "llm_provider": "openai"})
def test_extract_events_openai(mock_config, mock_call):
    """OpenAI provider returns parsed events."""
    events = extract_events_with_llm("some email text")
    assert len(events) == 1
    assert events[0]["date"] == "2026-02-10"


@patch("email_parser._load_llm_config", return_value={**FAKE_CONFIG, "llm_provider": "unsupported"})
def test_extract_events_unsupported_provider(mock_config):
    """Unsupported provider raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported llm_provider"):
        extract_events_with_llm("text")


# --- is_duplicate_event tests ---

EXISTING_EVENTS = [
    {
        "summary": "ParentEd Talks",
        "start": {"dateTime": "2026-02-10T12:00:00-08:00"},
        "end": {"dateTime": "2026-02-10T13:00:00-08:00"},
    },
]


@patch("email_parser._call_llm", return_value='{"is_duplicate": true}')
@patch("email_parser._load_llm_config", return_value=FAKE_CONFIG)
def test_is_duplicate_event_true(mock_config, mock_call):
    """LLM identifies a duplicate event."""
    new_event = {"date": "2026-02-10", "time": "12:00-13:00", "description": "ParentEd Talks"}
    assert is_duplicate_event(new_event, EXISTING_EVENTS) is True


@patch("email_parser._call_llm", return_value='{"is_duplicate": false}')
@patch("email_parser._load_llm_config", return_value=FAKE_CONFIG)
def test_is_duplicate_event_false(mock_config, mock_call):
    """LLM determines event is not a duplicate."""
    new_event = {"date": "2026-02-10", "time": "14:00-15:00", "description": "Science Fair"}
    assert is_duplicate_event(new_event, EXISTING_EVENTS) is False


def test_is_duplicate_event_no_existing():
    """Returns False immediately when no existing events."""
    new_event = {"date": "2026-02-10", "time": "12:00", "description": "Something"}
    assert is_duplicate_event(new_event, []) is False


# --- to_csv tests ---

def test_to_csv_writes_correct_format():
    """CSV output has the right headers and data."""
    events = [
        {"date": "2026-02-10", "time": "12:00-13:00", "description": "ParentEd Talks", "is_deadline": False},
        {"date": "2026-02-12", "time": "", "description": "Adventure Days", "is_deadline": False},
    ]
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        to_csv(events, path)
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-02-10"
        assert rows[0]["time"] == "12:00-13:00"
        assert rows[0]["description"] == "ParentEd Talks"
        assert rows[1]["time"] == ""
    finally:
        os.unlink(path)


def test_to_csv_writes_is_deadline_column():
    """CSV output includes the is_deadline column."""
    events = [
        {"date": "2026-02-10", "time": "12:00-13:00", "description": "ParentEd Talks", "is_deadline": False},
        {"date": "2026-02-14", "time": "", "description": "Registration Due", "is_deadline": True},
    ]
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        to_csv(events, path)
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "is_deadline" in reader.fieldnames
        assert rows[0]["is_deadline"] == "False"
        assert rows[1]["is_deadline"] == "True"
    finally:
        os.unlink(path)
