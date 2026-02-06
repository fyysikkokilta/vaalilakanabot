# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vaalilakanabot is a Telegram bot for managing guild election candidates and announcing new Discourse forum posts. It integrates with:
- Telegram (python-telegram-bot 22.3)
- Google Sheets (gspread) as the primary data store
- Discourse/Fiirumi forum for announcements

## Development Commands

### Running the Bot

```bash
# Local development
python vaalilakanabot.py

# With Docker (local build)
docker-compose up

# Production (pre-built image from GHCR)
docker-compose -f docker-compose.prod.yml up

# Update deployment script
./update-deployment.sh
```

### Linting

```bash
pip install pylint
pylint *.py
```

## Architecture

### Data Storage Strategy

**Google Sheets is the single source of truth** for all persistent data. The bot uses three worksheets:

1. **Election Structure** - Defines available roles (divisions, positions, types, deadlines)
2. **Applications** - User applications with status tracking
3. **Channels** - Registered Telegram chats for announcements

This design allows admins to manually edit data in Google Sheets and have changes sync automatically with the bot.

### Core Components

- **src/bot.py** - Main entry point, sets up handlers and job queue
- **src/sheets_data_manager.py** - High-level data operations (business logic layer)
- **src/sheets_manager.py** - Low-level Google Sheets operations with caching and queue batching
- **src/config.py** - Environment variable configuration
- **src/types.py** - TypedDict definitions for data structures

### Data Flow Pattern

1. User interactions → Application/Admin handlers
2. Handlers call DataManager methods (business logic)
3. DataManager delegates to SheetsManager (data layer)
4. SheetsManager uses queues to batch operations
5. Job queue flushes batched operations every 60 seconds

### Caching Strategy

SheetsManager uses TTL caches (5-minute expiry) for:
- `_roles_cache` - Election structure data
- `_applications_cache` - All applications
- `_channels_cache` - Registered channels

Caches are invalidated by the job queue every minute after flushing operations.

### Queue-Based Write Operations

To avoid excessive Google Sheets API calls, writes are batched in queues:
- `application_queue` - New applications
- `status_update_queue` - Application status changes (processed after applications)
- `channel_add_queue` / `channel_remove_queue` - Channel registrations

The `process_application_queue` job runs every 60 seconds to flush these queues in order.

### Job Queue Schedule

All jobs run every 60 seconds starting from August 10, 2025:
- `parse_fiirumi_posts` - Checks for new Discourse posts/questions
- `announce_new_responses` - Announces new forum responses (runs hourly)
- `update_election_sheet` - Updates the election sheet post on Discourse
- `process_application_queue` - Flushes queued Google Sheets operations

### Admin Approval Flow

Applications for elected positions (BOARD, ELECTED, AUDITOR types) require admin approval:
1. User submits application → queued with empty Status (pending)
2. Admin chat receives approval request with ✅ Approve / ❌ Reject buttons
3. Admin action → status updated to APPROVED or DENIED
4. Queue flush → Google Sheets updated
5. User notified of decision

Non-elected positions (NON_ELECTED type) are automatically approved.

### Conversation Handler States

Application flow uses ConversationHandler with states:
- `SELECTING_DIVISION` - Choose election division
- `SELECTING_ROLE` - Choose position within division
- `GIVING_NAME` - Enter full name
- `GIVING_EMAIL` - Enter email
- `CONFIRMING_APPLICATION` - Final confirmation

Both Finnish (`/hae`) and English (`/apply`) versions share the same state machine.

## Configuration

Environment variables are loaded from `bot.env` (see `bot.env.example`):

- **VAALILAKANABOT_TOKEN** - Telegram bot token from BotFather
- **ADMIN_CHAT_ID** - Telegram group ID for admin commands
- **GOOGLE_SHEET_URL** - Full URL of Google Sheets document
- **BASE_URL** - Discourse server base URL
- **API_KEY** / **API_USERNAME** - Discourse API credentials
- **TOPIC_LIST_URL** - Discourse category JSON for introductions
- **QUESTION_LIST_URL** - Discourse category JSON for questions
- **VAALILAKANA_POST_URL** - Discourse post to update with election sheet

Google credentials must be in `google_credentials.json` at project root (gitignored).

## Google Sheets Structure

### Election Structure Sheet

| Column | Field       | Type                                    |
|--------|-------------|-----------------------------------------|
| A      | ID          | Auto-generated UUID                     |
| B      | Division_FI | Finnish division name                   |
| C      | Division_EN | English division name                   |
| D      | Role_FI     | Finnish role name                       |
| E      | Role_EN     | English role name                       |
| F      | Type        | BOARD, ELECTED, NON_ELECTED, or AUDITOR |
| G      | Amount      | Number of positions                     |
| H      | Deadline    | Format: dd.mm. (day.month.)             |

### Applications Sheet

| Column | Field        | Note                                    |
|--------|--------------|-----------------------------------------|
| A      | Timestamp    | ISO format                              |
| B      | Role_ID      | References Election Structure ID        |
| C      | Telegram_ID  | User's numeric Telegram ID              |
| D      | Name         | Full name                               |
| E      | Email        | Contact email                           |
| F      | Telegram     | @username                               |
| G      | Fiirumi_Post | Link to forum introduction              |
| H      | Status       | APPROVED, DENIED, REMOVED, ELECTED, "" |
| I      | Language     | fi or en (for notifications)            |

Empty Status means pending approval.

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
- **Linting**: Runs pylint on all Python files
- **Build**: Builds and pushes Docker images to `ghcr.io/fyysikkokilta/vaalilakanabot`
- Images are tagged with branch name, commit SHA, and `latest` for master branch
- Only pushes images on master branch (not PRs)

## Code Patterns

### Localization

Commands come in Finnish and English pairs:
- `/hae` and `/apply` - Start application
- `/lakana` and `/sheet` - Show election sheet
- `/hakemukset` and `/applications` - Show user's applications
- `/apua` and `/help` - Show help

Role names and divisions have `_FI` and `_EN` suffixes in data structures.

### Election Sheet Preamble

The `update_election_sheet` job in `src/sheet_updater.py` supports preserving a preamble in the Discourse post:
- Fetches current post content before updating
- Looks for the marker: `---SHEET STARTS HERE---`
- Preserves everything above the marker when updating the sheet
- If no marker found, replaces entire post (no preamble preservation)

This allows admins to add instructions or announcements that persist across automated updates.

### Error Handling and Resilience

- **API retry logic**: All Google Sheets operations use exponential backoff retry for transient errors (503, 502, 500, 504, 429)
- **Last known values**: Persists last successful fetch to prevent data loss when API calls fail
- Failed channel messages automatically unregister the channel
- Queue operations log warnings on failure but don't crash the bot
- Google Sheets connection failures raise exceptions on init

### Adding New Roles

Admins can add roles directly in Google Sheets without bot commands:
1. Add new row to Election Structure sheet
2. ID will auto-generate if left empty
3. Type must be BOARD, ELECTED, NON_ELECTED, or AUDITOR
4. Deadline format must be exactly `dd.mm.`
5. Bot picks up changes automatically via cache invalidation
