"""CLI entry point for Google Calendar operations."""

import argparse
from datetime import datetime

from calendar_service import authenticate, list_events, create_event, get_event, delete_event


def cmd_list(args):
    service = authenticate()
    events = list_events(service, max_results=args.max)
    if not events:
        print("No upcoming events found.")
        return
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        print(f"{start}  {event.get('summary', '(no title)')}  [id: {event['id']}]")


def cmd_create(args):
    service = authenticate()
    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)
    event = create_event(
        service,
        summary=args.summary,
        start=start,
        end=end,
        description=args.description,
        location=args.location,
    )
    print(f"Created event: {event.get('htmlLink')}")


def cmd_get(args):
    service = authenticate()
    event = get_event(service, args.id)
    start = event["start"].get("dateTime", event["start"].get("date"))
    end = event["end"].get("dateTime", event["end"].get("date"))
    print(f"Summary:     {event.get('summary', '(no title)')}")
    print(f"Start:       {start}")
    print(f"End:         {end}")
    print(f"Location:    {event.get('location', '')}")
    print(f"Description: {event.get('description', '')}")
    print(f"ID:          {event['id']}")


def cmd_delete(args):
    service = authenticate()
    delete_event(service, args.id)
    print(f"Deleted event {args.id}")


def main():
    parser = argparse.ArgumentParser(description="Google Calendar CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List upcoming events")
    p_list.add_argument("--max", type=int, default=10, help="Max number of events")
    p_list.set_defaults(func=cmd_list)

    # create
    p_create = subparsers.add_parser("create", help="Create a calendar event")
    p_create.add_argument("--summary", required=True, help="Event title")
    p_create.add_argument("--start", required=True, help="Start time (YYYY-MM-DDTHH:MM)")
    p_create.add_argument("--end", required=True, help="End time (YYYY-MM-DDTHH:MM)")
    p_create.add_argument("--description", help="Event description")
    p_create.add_argument("--location", help="Event location")
    p_create.set_defaults(func=cmd_create)

    # get
    p_get = subparsers.add_parser("get", help="Get event details")
    p_get.add_argument("--id", required=True, help="Event ID")
    p_get.set_defaults(func=cmd_get)

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete an event")
    p_delete.add_argument("--id", required=True, help="Event ID")
    p_delete.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
