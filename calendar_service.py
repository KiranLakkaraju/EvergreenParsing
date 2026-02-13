"""Google Calendar API wrapper with OAuth 2.0 authentication."""

import json
import os
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config(config_path=CONFIG_PATH):
    """Load configuration from config.json.

    Returns a dict with config values. Defaults to calendar_id="primary"
    if the file is missing or the key is absent.
    """
    config = {"calendar_id": "primary"}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config.update(json.load(f))
    return config


def authenticate(token_path=TOKEN_PATH, credentials_path=CREDENTIALS_PATH):
    """Authenticate with Google Calendar API via OAuth 2.0.

    Loads saved tokens from token_path if available, refreshes expired tokens,
    or launches browser consent flow if no valid tokens exist.

    Returns an authorized Google Calendar API service object.
    """
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def list_events(service, max_results=10, time_min=None, calendar_id=None):
    """List upcoming events from the configured calendar.

    Args:
        service: Authorized Google Calendar API service object.
        max_results: Maximum number of events to return.
        time_min: Only return events after this datetime. Defaults to now.
        calendar_id: Calendar ID to use. Defaults to config value.

    Returns:
        List of event dicts.
    """
    if calendar_id is None:
        calendar_id = load_config()["calendar_id"]
    if time_min is None:
        time_min = datetime.now(timezone.utc).isoformat()
    else:
        time_min = time_min.isoformat()

    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def create_event(service, summary, start, end, description=None, location=None, timezone="America/Los_Angeles", calendar_id=None):
    """Create a calendar event.

    Args:
        service: Authorized Google Calendar API service object.
        summary: Event title.
        start: Event start as a datetime object.
        end: Event end as a datetime object.
        description: Optional event description.
        location: Optional event location.
        timezone: Timezone string (default: America/Los_Angeles).
        calendar_id: Calendar ID to use. Defaults to config value.

    Returns:
        The created event dict.
    """
    if calendar_id is None:
        calendar_id = load_config()["calendar_id"]
    event_body = {
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
    }
    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location

    return service.events().insert(calendarId=calendar_id, body=event_body).execute()


def get_event(service, event_id, calendar_id=None):
    """Retrieve a single event by ID.

    Args:
        service: Authorized Google Calendar API service object.
        event_id: The event ID string.
        calendar_id: Calendar ID to use. Defaults to config value.

    Returns:
        The event dict.
    """
    if calendar_id is None:
        calendar_id = load_config()["calendar_id"]
    return service.events().get(calendarId=calendar_id, eventId=event_id).execute()


def delete_event(service, event_id, calendar_id=None):
    """Delete an event by ID.

    Args:
        service: Authorized Google Calendar API service object.
        event_id: The event ID string.
        calendar_id: Calendar ID to use. Defaults to config value.
    """
    if calendar_id is None:
        calendar_id = load_config()["calendar_id"]
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
