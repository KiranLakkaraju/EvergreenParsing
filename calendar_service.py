"""Google Calendar API wrapper with OAuth 2.0 authentication."""

import os
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")


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


def list_events(service, max_results=10, time_min=None):
    """List upcoming events from the user's primary calendar.

    Args:
        service: Authorized Google Calendar API service object.
        max_results: Maximum number of events to return.
        time_min: Only return events after this datetime. Defaults to now.

    Returns:
        List of event dicts.
    """
    if time_min is None:
        time_min = datetime.now(timezone.utc).isoformat()
    else:
        time_min = time_min.isoformat()

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def create_event(service, summary, start, end, description=None, location=None, timezone="America/Los_Angeles"):
    """Create a calendar event.

    Args:
        service: Authorized Google Calendar API service object.
        summary: Event title.
        start: Event start as a datetime object.
        end: Event end as a datetime object.
        description: Optional event description.
        location: Optional event location.
        timezone: Timezone string (default: America/Los_Angeles).

    Returns:
        The created event dict.
    """
    event_body = {
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
    }
    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location

    return service.events().insert(calendarId="primary", body=event_body).execute()


def get_event(service, event_id):
    """Retrieve a single event by ID.

    Args:
        service: Authorized Google Calendar API service object.
        event_id: The event ID string.

    Returns:
        The event dict.
    """
    return service.events().get(calendarId="primary", eventId=event_id).execute()


def delete_event(service, event_id):
    """Delete an event by ID.

    Args:
        service: Authorized Google Calendar API service object.
        event_id: The event ID string.
    """
    service.events().delete(calendarId="primary", eventId=event_id).execute()
