# EvergreenParsing
Small script to parse Evergreen emails and create calendar events from them.

## Setup

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the Google Calendar API
3. Create an OAuth 2.0 Client ID (Desktop application)
4. Download `credentials.json` into the project root
5. Create `config.json` in the project root:
   ```json
   {
       "calendar_id": "your_calendar_id_here",
       "llm_provider": "anthropic",
       "llm_model": "claude-sonnet-4-5-20250929",
       "llm_api_key": "sk-ant-..."
   }
   ```
   - `calendar_id`: Google Calendar ID (defaults to `"primary"` if omitted)
   - `llm_provider`: `"anthropic"` or `"openai"`
   - `llm_model`: Model ID string
   - `llm_api_key`: API key for the provider
6. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
7. First run will open a browser for Google OAuth consent

## Quick Start

To process a school bulletin email and add events to your calendar in one step:

```bash
python main.py process --input "data/Monday Bulletin 1.26.2026.eml"
```

This will:
1. Parse the `.eml` file and extract events using the configured LLM
2. Check each event against your Google Calendar for duplicates
3. Create only new events, skipping any that already exist

## All Commands

| Command | Description |
|---------|-------------|
| `python main.py process --input FILE.eml` | Parse email and add events to calendar (skips duplicates) |
| `python main.py parse --input FILE.eml [--output FILE.csv]` | Parse email to CSV only |
| `python main.py add --input FILE.csv` | Add events from CSV to calendar (skips duplicates) |
| `python main.py list [--max N]` | List upcoming calendar events |
| `python main.py create --summary "..." --start "..." --end "..."` | Create a single event |
| `python main.py get --id EVENT_ID` | Get event details |
| `python main.py delete --id EVENT_ID` | Delete an event |

## Running Tests

```bash
pytest tests/
```
