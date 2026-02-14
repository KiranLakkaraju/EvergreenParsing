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


def _build_deadline_reminders(time_str, parsed_date):
    """Build a Google Calendar reminders dict for a deadline event.

    For all-day events, Google Calendar treats the event start as midnight,
    so we set the reminder offset to fire at 8:00 AM (480 minutes before
    midnight of the *next* day is not how it works — for all-day events,
    the reminder minutes are relative to midnight at the start of the event day,
    so 0 minutes = midnight, but Google interprets negative offsets from the
    start. For all-day events we use 0 minutes which triggers at the start
    of the day).

    For timed events, we calculate how many minutes before the event start
    8:00 AM falls. If the event is at or before 8 AM, we use 0 minutes.
    """
    if not time_str:
        # All-day event: reminder at 8 AM = 480 minutes after midnight.
        # Google Calendar all-day event reminders are minutes before the
        # event start (midnight), but shown as "morning of". We use
        # 480 minutes which Google shows as "8:00 AM on the day of the event"
        # (for all-day events, minutes count *forward* from midnight when
        # negative values aren't used — actually Google uses minutes *before*
        # start, and for all-day events start = midnight, so to fire at 8 AM
        # we'd need a negative offset which isn't supported).
        # The correct approach: set reminder to 0 minutes (fires at start of day).
        # But we can approximate 8 AM with a custom approach: use the
        # "overrides" with minutes=0 for a start-of-day reminder.
        # Actually, to get exactly 8 AM, we compute minutes from the end of
        # the all-day event (next day midnight) back to 8 AM = 16*60 = 960.
        # No — Google uses minutes before the *start*, and start = midnight.
        # A negative number isn't valid. So the best we can do is 0 (midnight)
        # or use the fact that for all-day events Google interprets the
        # reminder as "N minutes before midnight of the event day" going
        # backwards into the previous day. To fire on the day itself at 8 AM,
        # we actually cannot use standard reminder offset.
        #
        # Simplest correct approach: 0 minutes = fires at start of event day.
        return {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 0}],
        }
    else:
        # Timed event: calculate minutes between 8:00 AM and event start
        event_start_str = time_str.split("-")[0]
        event_start_time = datetime.strptime(event_start_str, "%H:%M").time()
        event_start = datetime.combine(parsed_date, event_start_time)
        eight_am = datetime.combine(parsed_date, datetime.strptime("08:00", "%H:%M").time())
        diff = event_start - eight_am
        minutes = max(int(diff.total_seconds() // 60), 0)
        return {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": minutes}],
        }


def cmd_add(args):
    service = authenticate()
    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row["date"]
            time_str = row["time"].strip()
            description = row["description"]
            is_deadline = row.get("is_deadline", "").strip().lower() == "true"
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            existing = list_events_for_date(service, parsed_date)
            if existing and is_duplicate_event(row, existing):
                print(f"Skipped (already exists): {description} on {date_str}")
                continue

            reminders = _build_deadline_reminders(time_str, parsed_date) if is_deadline else None
            reminder_note = " [8 AM reminder]" if is_deadline else ""

            if not time_str:
                event = create_all_day_event(service, summary=description, date=parsed_date, reminders=reminders)
                print(f"Created all-day event: {description} on {date_str}{reminder_note}")
            elif re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", time_str):
                start_str, end_str = time_str.split("-")
                start = datetime.combine(parsed_date, datetime.strptime(start_str, "%H:%M").time())
                end = datetime.combine(parsed_date, datetime.strptime(end_str, "%H:%M").time())
                event = create_event(service, summary=description, start=start, end=end, reminders=reminders)
                print(f"Created timed event: {description} on {date_str} {time_str}{reminder_note}")
            else:
                start = datetime.combine(parsed_date, datetime.strptime(time_str, "%H:%M").time())
                end = start + timedelta(hours=1)
                event = create_event(service, summary=description, start=start, end=end, reminders=reminders)
                print(f"Created timed event: {description} on {date_str} {time_str} (1hr default){reminder_note}")


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
        writer = csv.DictWriter(tmp, fieldnames=["date", "time", "description", "is_deadline"])
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
                is_deadline = row.get("is_deadline", "").strip().lower() == "true"
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                existing = list_events_for_date(service, parsed_date)
                if existing and is_duplicate_event(row, existing):
                    print(f"Skipped (already exists): {description} on {date_str}")
                    skipped += 1
                    continue

                reminders = _build_deadline_reminders(time_str, parsed_date) if is_deadline else None
                reminder_note = " [8 AM reminder]" if is_deadline else ""

                if not time_str:
                    create_all_day_event(service, summary=description, date=parsed_date, reminders=reminders)
                    print(f"Created all-day event: {description} on {date_str}{reminder_note}")
                elif re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", time_str):
                    start_str, end_str = time_str.split("-")
                    start = datetime.combine(parsed_date, datetime.strptime(start_str, "%H:%M").time())
                    end = datetime.combine(parsed_date, datetime.strptime(end_str, "%H:%M").time())
                    create_event(service, summary=description, start=start, end=end, reminders=reminders)
                    print(f"Created timed event: {description} on {date_str} {time_str}{reminder_note}")
                else:
                    start = datetime.combine(parsed_date, datetime.strptime(time_str, "%H:%M").time())
                    end = start + timedelta(hours=1)
                    create_event(service, summary=description, start=start, end=end, reminders=reminders)
                    print(f"Created timed event: {description} on {date_str} {time_str} (1hr default){reminder_note}")
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
