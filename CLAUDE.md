# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EvergreenParsing is a Python project that parses Evergreen emails and creates Google Calendar events from them. Licensed under GPL-3.0.

## Setup

1. Create a Google Cloud project at console.cloud.google.com
2. Enable the Google Calendar API
3. Create an OAuth 2.0 Client ID (Desktop application)
4. Download `credentials.json` into the project root
5. Create `config.json` in the project root to specify a calendar ID and LLM settings:
   ```json
   {
       "calendar_id": "your_calendar_id_here",
       "llm_provider": "anthropic",
       "llm_model": "claude-sonnet-4-5-20250929",
       "llm_api_key": "sk-ant-..."
   }
   ```
   - `calendar_id`: Google Calendar ID (defaults to `"primary"` if omitted)
   - `llm_provider`: `"anthropic"` or `"openai"` (required for parse command)
   - `llm_model`: Model ID string (required for parse command)
   - `llm_api_key`: API key for the provider (required for parse command)
   This file is gitignored.
6. Install dependencies: `pip install -r requirements.txt`
7. First run of `python main.py list` will open a browser for OAuth consent

## Commands

- **Install deps:** `pip install -r requirements.txt`
- **Run tests:** `pytest tests/`
- **List events:** `python main.py list [--max N]`
- **Create event:** `python main.py create --summary "..." --start "YYYY-MM-DDTHH:MM" --end "YYYY-MM-DDTHH:MM" [--description "..."] [--location "..."]`
- **Get event:** `python main.py get --id EVENT_ID`
- **Delete event:** `python main.py delete --id EVENT_ID`
- **Process email end-to-end:** `python main.py process --input "data/Monday Bulletin 2.9.2026.eml"` (parses email, checks for duplicates, creates events)
- **Parse email only:** `python main.py parse --input "data/Monday Bulletin 2.9.2026.eml" --output parsed_events.csv`
- **Add parsed events to calendar:** `python main.py add --input parsed_events.csv` (skips duplicate events using LLM comparison against existing calendar events)

## Architecture

- `config.json` — User-specific configuration (gitignored). Contains `calendar_id` and LLM settings used by API methods.
- `calendar_service.py` — Core library: `load_config` reads `config.json`, `authenticate` handles OAuth 2.0, and `list_events`/`create_event`/`get_event`/`delete_event` wrap the Google Calendar API
- `email_parser.py` — Parses `.eml` files, extracts event dates/times via a configurable LLM (Anthropic or OpenAI), and outputs CSV. The LLM also classifies events as deadlines (`is_deadline`); deadline events automatically get an 8 AM morning popup reminder in Google Calendar
- `main.py` — CLI entry point using argparse with subcommands
- `tests/test_calendar_service.py` — Unit tests with mocked API calls (no credentials needed)
- `tests/test_email_parser.py` — Unit tests for email parsing with mocked LLM calls
