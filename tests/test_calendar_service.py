"""Unit tests for calendar_service.py — all Google API calls are mocked."""

from datetime import datetime
from unittest.mock import MagicMock, mock_open, patch

import pytest

from calendar_service import authenticate, list_events, create_event, get_event, delete_event


# --- authenticate tests ---

@patch("calendar_service.build")
@patch("calendar_service.Credentials")
@patch("calendar_service.os.path.exists", return_value=True)
def test_authenticate_existing_valid_token(mock_exists, mock_creds_cls, mock_build):
    """When token.json exists and credentials are valid, return service without browser flow."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds_cls.from_authorized_user_file.return_value = mock_creds

    service = authenticate(token_path="token.json", credentials_path="credentials.json")

    mock_creds_cls.from_authorized_user_file.assert_called_once_with("token.json", authenticate.__module__ and ["https://www.googleapis.com/auth/calendar"])
    mock_build.assert_called_once_with("calendar", "v3", credentials=mock_creds)
    assert service == mock_build.return_value


@patch("calendar_service.build")
@patch("calendar_service.Request")
@patch("calendar_service.Credentials")
@patch("calendar_service.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open)
def test_authenticate_expired_token_refreshes(mock_file, mock_exists, mock_creds_cls, mock_request, mock_build):
    """When token is expired but refreshable, refresh and save it."""
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh_tok"
    mock_creds_cls.from_authorized_user_file.return_value = mock_creds

    service = authenticate(token_path="token.json", credentials_path="credentials.json")

    mock_creds.refresh.assert_called_once_with(mock_request.return_value)
    mock_file.assert_called_once_with("token.json", "w")
    mock_file().write.assert_called_once_with(mock_creds.to_json.return_value)
    assert service == mock_build.return_value


@patch("calendar_service.build")
@patch("calendar_service.InstalledAppFlow")
@patch("calendar_service.os.path.exists", return_value=False)
@patch("builtins.open", new_callable=mock_open)
def test_authenticate_no_token_runs_flow(mock_file, mock_exists, mock_flow_cls, mock_build):
    """When no token.json exists, run the full OAuth consent flow."""
    mock_flow = MagicMock()
    mock_flow_cls.from_client_secrets_file.return_value = mock_flow
    mock_creds = mock_flow.run_local_server.return_value

    service = authenticate(token_path="token.json", credentials_path="credentials.json")

    mock_flow_cls.from_client_secrets_file.assert_called_once()
    mock_flow.run_local_server.assert_called_once_with(port=0)
    mock_file().write.assert_called_once_with(mock_creds.to_json.return_value)
    assert service == mock_build.return_value


# --- list_events tests ---

def test_list_events():
    """Verify list_events calls the API with correct parameters and returns items."""
    mock_service = MagicMock()
    fake_items = [
        {"id": "1", "summary": "Meeting", "start": {"dateTime": "2026-02-13T10:00:00"}},
        {"id": "2", "summary": "Lunch", "start": {"dateTime": "2026-02-13T12:00:00"}},
    ]
    mock_service.events().list().execute.return_value = {"items": fake_items}

    result = list_events(mock_service, max_results=5)

    mock_service.events().list.assert_called_with(
        calendarId="primary",
        timeMin=mock_service.events().list.call_args.kwargs["timeMin"],
        maxResults=5,
        singleEvents=True,
        orderBy="startTime",
    )
    assert result == fake_items


def test_list_events_empty():
    """Handles case where no events are returned."""
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {}

    result = list_events(mock_service)

    assert result == []


# --- create_event tests ---

def test_create_event():
    """Verify event body is built correctly from arguments."""
    mock_service = MagicMock()
    fake_event = {"id": "abc123", "summary": "Test"}
    mock_service.events().insert().execute.return_value = fake_event

    start = datetime(2026, 2, 13, 10, 0)
    end = datetime(2026, 2, 13, 11, 0)
    result = create_event(
        mock_service,
        summary="Test",
        start=start,
        end=end,
        description="A test event",
        location="Room 1",
    )

    mock_service.events().insert.assert_called_with(
        calendarId="primary",
        body={
            "summary": "Test",
            "start": {"dateTime": start.isoformat(), "timeZone": "America/Los_Angeles"},
            "end": {"dateTime": end.isoformat(), "timeZone": "America/Los_Angeles"},
            "description": "A test event",
            "location": "Room 1",
        },
    )
    assert result == fake_event


# --- get_event tests ---

def test_get_event():
    """Verify event_id is passed to the API."""
    mock_service = MagicMock()
    fake_event = {"id": "evt123", "summary": "Meeting"}
    mock_service.events().get().execute.return_value = fake_event

    result = get_event(mock_service, "evt123")

    mock_service.events().get.assert_called_with(calendarId="primary", eventId="evt123")
    assert result == fake_event


# --- delete_event tests ---

def test_delete_event():
    """Verify event_id is passed to the delete API call."""
    mock_service = MagicMock()

    delete_event(mock_service, "evt456")

    mock_service.events().delete.assert_called_with(calendarId="primary", eventId="evt456")
    mock_service.events().delete().execute.assert_called_once()
