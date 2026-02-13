# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EvergreenParsing is a Python project that parses Evergreen emails and creates Google Calendar events from them. Licensed under GPL-3.0.

## Setup

1. Create a Google Cloud project at console.cloud.google.com
2. Enable the Google Calendar API
3. Create an OAuth 2.0 Client ID (Desktop application)
4. Download `credentials.json` into the project root
5. Install dependencies: `pip install -r requirements.txt`
6. First run of `python main.py list` will open a browser for OAuth consent

## Commands

- **Install deps:** `pip install -r requirements.txt`
- **Run tests:** `pytest tests/`
- **List events:** `python main.py list [--max N]`
- **Create event:** `python main.py create --summary "..." --start "YYYY-MM-DDTHH:MM" --end "YYYY-MM-DDTHH:MM" [--description "..."] [--location "..."]`
- **Get event:** `python main.py get --id EVENT_ID`
- **Delete event:** `python main.py delete --id EVENT_ID`

## Architecture

- `calendar_service.py` — Core library: OAuth 2.0 authentication and Google Calendar API wrapper functions (`authenticate`, `list_events`, `create_event`, `get_event`, `delete_event`)
- `main.py` — CLI entry point using argparse with subcommands
- `tests/test_calendar_service.py` — Unit tests with mocked API calls (no credentials needed)
