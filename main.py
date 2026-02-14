"""CLI entry point for Google Calendar operations."""

import argparse
import csv
import re
from datetime import datetime, timedelta

from calendar_service import authenticate, list_events, list_events_for_date, create_event, create_all_day_event, get_event, delete_event
from email_parser import parse_eml, extract_events_with_llm, is_duplicate_event, to_csv


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


def cmd_add(args):
    service = authenticate()
    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row["date"]
            time_str = row["time"].strip()
            description = row["description"]
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            existing = list_events_for_date(service, parsed_date)
            if existing and is_duplicate_event(row, existing):
                print(f"Skipped (already exists): {description} on {date_str}")
                continue

            if not time_str:
                event = create_all_day_event(service, summary=description, date=parsed_date)
                print(f"Created all-day event: {description} on {date_str}")
            elif re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", time_str):
                start_str, end_str = time_str.split("-")
                start = datetime.combine(parsed_date, datetime.strptime(start_str, "%H:%M").time())
                end = datetime.combine(parsed_date, datetime.strptime(end_str, "%H:%M").time())
                event = create_event(service, summary=description, start=start, end=end)
                print(f"Created timed event: {description} on {date_str} {time_str}")
            else:
                start = datetime.combine(parsed_date, datetime.strptime(time_str, "%H:%M").time())
                end = start + timedelta(hours=1)
                event = create_event(service, summary=description, start=start, end=end)
                print(f"Created timed event: {description} on {date_str} {time_str} (1hr default)")


def cmd_parse(args):
    text = parse_eml(args.input)
    events = extract_events_with_llm(text)
    to_csv(events, args.output)
    print(f"Extracted {len(events)} events to {args.output}")


def cmd_process(args):
    """Parse an .eml file and add events to Google Calendar in one step."""
    import tempfile

    # Step 1: Parse the email
    print(f"Parsing {args.input}...")
    text = parse_eml(args.input)
    events = extract_events_with_llm(text)
    print(f"Found {len(events)} events.")

    if not events:
        return

    # Step 2: Write to a temporary CSV and add events
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as tmp:
        tmp_path = tmp.name
        writer = csv.DictWriter(tmp, fieldnames=["date", "time", "description"])
        writer.writeheader()
        writer.writerows(events)

    created = 0
    skipped = 0
    try:
        service = authenticate()
        with open(tmp_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row["date"]
                time_str = row["time"].strip()
                description = row["description"]
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                existing = list_events_for_date(service, parsed_date)
                if existing and is_duplicate_event(row, existing):
                    print(f"Skipped (already exists): {description} on {date_str}")
                    skipped += 1
                    continue

                if not time_str:
                    create_all_day_event(service, summary=description, date=parsed_date)
                    print(f"Created all-day event: {description} on {date_str}")
                elif re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", time_str):
                    start_str, end_str = time_str.split("-")
                    start = datetime.combine(parsed_date, datetime.strptime(start_str, "%H:%M").time())
                    end = datetime.combine(parsed_date, datetime.strptime(end_str, "%H:%M").time())
                    create_event(service, summary=description, start=start, end=end)
                    print(f"Created timed event: {description} on {date_str} {time_str}")
                else:
                    start = datetime.combine(parsed_date, datetime.strptime(time_str, "%H:%M").time())
                    end = start + timedelta(hours=1)
                    create_event(service, summary=description, start=start, end=end)
                    print(f"Created timed event: {description} on {date_str} {time_str} (1hr default)")
                created += 1
    finally:
        import os
        os.unlink(tmp_path)

    print(f"\nDone: {created} created, {skipped} skipped (duplicates).")


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

    # add
    p_add = subparsers.add_parser("add", help="Add parsed events from CSV to Google Calendar")
    p_add.add_argument("--input", required=True, help="Path to parsed events CSV")
    p_add.set_defaults(func=cmd_add)

    # parse
    p_parse = subparsers.add_parser("parse", help="Parse an .eml file for events using LLM")
    p_parse.add_argument("--input", required=True, help="Path to .eml file")
    p_parse.add_argument("--output", default="parsed_events.csv", help="Output CSV path")
    p_parse.set_defaults(func=cmd_parse)

    # process
    p_process = subparsers.add_parser("process", help="Parse an .eml file and add events to Google Calendar (skips duplicates)")
    p_process.add_argument("--input", required=True, help="Path to .eml file")
    p_process.set_defaults(func=cmd_process)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
