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
pylint src/*.py
```

## Architecture

### Data Storage Strategy

**Google Sheets is the single source of truth** for all persistent data. The bot uses four worksheets:

1. **Election Structure** - Defines available roles (divisions, positions, types, deadlines)
2. **Applications** - User applications with status tracking (linked to Users by Telegram_ID; optional Group_ID for group applications)
3. **Users** - User registration (name, email, consent). Required before applying; `/register` and `/rekisteroidy` upsert here.
4. **Channels** - Registered Telegram chats for announcements

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
- `_users_cache` - Users sheet (registration data)

Caches are invalidated by the job queue every minute after flushing operations.

### Queue-Based Write Operations

To avoid excessive Google Sheets API calls, writes are batched in queues:

- `application_queue` - New applications
- `status_update_queue` - Application status changes and Group_ID updates (processed after applications)
- `user_upsert_queue` - User registration/updates (flushed first so users exist before applications)
- `channel_add_queue` / `channel_remove_queue` - Channel registrations

The `process_application_queue` job runs every 60 seconds to flush these queues in order (users → applications → status updates → channels).

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

**Application flow** (`/hae`, `/apply`): Requires the user to be registered (Users sheet). If not, the bot prompts to use `/register` or `/rekisteroidy`. States:

- `SELECTING_DIVISION` - Choose election division
- `SELECTING_ROLE` - Choose position within division
- `CONFIRMING_APPLICATION` - Confirm with registered name/email (no name/email prompts; data from Users sheet)

Both Finnish (`/hae`) and English (`/apply`) share the same state machine.

**Registration flow** (`/rekisteroidy`, `/register`): **src/register_handlers.py**

- `REGISTER_NAME` - Enter full name
- `REGISTER_EMAIL` - Enter email
- `REGISTER_CONSENT` - Yes/No for showing name on guild website

Saving upserts the user into the Users sheet. Running the command again acts as an update (same flow, overwrites user row).

## Configuration

Environment variables are loaded from `bot.env` (see `bot.env.example`):

- **VAALILAKANABOT_TOKEN** - Telegram bot token from BotFather
- **ADMIN_CHAT_ID** - Telegram group ID for admin commands
- **GOOGLE_SHEET_URL** - Full URL of Google Sheets document
- **BASE_URL** - Discourse server base URL
- **API_KEY** / **API_USERNAME** - Discourse API credentials
- **ELECTION_YEAR** (required) - Target election year (e.g. 2025). Used for automatic Discourse area generation and to derive all Fiirumi URLs (introductions, questions, election sheet post). Set to the current election year.

Google credentials must be in `google_credentials.json` at project root (gitignored).

## Automatic Fiirumi Area Generation

The bot requires `ELECTION_YEAR` to be set (to the current election year). It uses this to create Discourse categories and to derive all Fiirumi URLs.

**Module**: `src/fiirumi_area_generator.py`

**Generated structure**:

- Parent category: `vaalipeli-{year}` (e.g., "Vaalipeli 2025") — election sheet topic is posted here
- Subcategory: `esittelyt` (Introductions)
- Subcategory: `kysymykset` (Questions)
- Election sheet topic: a topic titled "Vaalilakana {year}" in the parent category (first post URL is used as VAALILAKANA_POST_URL when not set)

**Behavior**:

- Runs once during bot initialization in `post_init()`
- Checks if categories already exist before creating
- Only generates when current year == ELECTION_YEAR
- Logs category URLs for convenience
- Uses Discourse Categories API with proper authentication

## Google Sheets Structure

### Election Structure Sheet

| Column | Field       | Type                                    |
| ------ | ----------- | --------------------------------------- |
| A      | ID          | Auto-generated UUID                     |
| B      | Division_FI | Finnish division name                   |
| C      | Division_EN | English division name                   |
| D      | Role_FI     | Finnish role name                       |
| E      | Role_EN     | English role name                       |
| F      | Type        | BOARD, ELECTED, NON_ELECTED, or AUDITOR |
| G      | Amount      | Number of positions                     |
| H      | Deadline    | Format: dd.mm. (day.month.)             |

### Applications Sheet

| Column | Field        | Note                                                                |
| ------ | ------------ | ------------------------------------------------------------------- |
| A      | Timestamp    | ISO format                                                          |
| B      | Role_ID      | References Election Structure ID                                    |
| C      | Telegram_ID  | User's numeric Telegram ID (links to Users for name/email/telegram) |
| D      | Fiirumi_Post | Link to forum introduction                                          |
| E      | Status       | APPROVED, DENIED, REMOVED, ELECTED, or "" (pending)                 |
| F      | Language     | fi or en (for notifications)                                        |
| G      | Group_ID     | Shared UUID for group applications; same value → one line in sheet  |

Display name/email/telegram are resolved from the Users sheet via `Telegram_ID`. Empty Status means pending approval.

### Users Sheet

| Column | Field                   | Note                                                           |
| ------ | ----------------------- | -------------------------------------------------------------- |
| A      | Telegram_ID             | User's numeric Telegram ID (primary key)                       |
| B      | Name                    | Full name                                                      |
| C      | Email                   | Contact email                                                  |
| D      | Telegram                | @username                                                      |
| E      | Show_On_Website_Consent | TRUE/FALSE - consent to show person on website's official page |
| F      | Updated_At              | ISO timestamp of last update                                   |

**Purpose**:

- Users register via `/register` (English) or `/rekisteroidy` (Finnish) before applying
- Applying uses this data (no name/email asked in apply flow); `/hakemukset` and `/applications` require registration
- Single consent field controls export (e.g. `export_officials_website`) and display on the website's official page
- Running `/register` or `/rekisteroidy` again upserts the user (update flow)

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):

- **Linting**: Runs pylint on all Python files
- **Build**: Builds and pushes Docker images to `ghcr.io/fyysikkokilta/vaalilakanabot`
- Images are tagged with branch name, commit SHA, and `latest` for master branch
- Only pushes images on master branch (not PRs)

## Code Patterns

### Localization

Commands come in Finnish and English pairs:

- `/start`, `/rekisteroidy` and `/register` - Register or update user info (required before applying; `/start` triggers English flow in private chat)
- `/hae` and `/apply` - Start application (checks registration first)
- `/lakana` and `/sheet` - Show election sheet
- `/hakemukset` and `/applications` - Show user's applications (requires registration)
- `/apua` and `/help` - Show help

Role names and divisions have `_FI` and `_EN` suffixes in data structures.

### Election Sheet Preamble

The `update_election_sheet` job in `src/sheet_updater.py` supports preserving a preamble in the Discourse post:

- Fetches current post content before updating
- Looks for the heading: `# VAALILAKANA {year} / ELECTION SHEET {year}`
- Preserves everything above that heading when updating the sheet
- If heading not found, replaces entire post (no preamble preservation)

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

## User Registration

- **Commands**: `/start` / `/register` (English) and `/rekisteroidy` (Finnish), private chat only. Implemented in **src/register_handlers.py**. `/start` triggers the English registration flow.
- **Flow**: User is asked for full name, email, and consent (show on website's official page Yes/No). Data is upserted into the Users sheet. Running the command again shows an update intro and the same steps, then overwrites the user row.
- **Gating**: Applying (`/hae`, `/apply`) and viewing applications (`/hakemukset`, `/applications`) require the user to exist in the Users sheet; otherwise the bot replies with a prompt to register first.
- **Application data**: Applications store only `Telegram_ID` (and application fields). Name, email, and Telegram handle are resolved from the Users sheet via `DataManager.get_applicant_display()` and by enriching applicant lists in `_applicants_for_role_enriched()` (called via the `vaalilakana_full` property in `sheets_data_manager.py`). Admin approval and admin commands (remove, elected, fiirumi, combine) resolve names from Users by `Telegram_ID`.
- **Caching**: Users sheet is cached and invalidated with the rest after queue flush; `user_upsert_queue` is flushed first so users exist before new applications reference them.

## Group Applications

- **Linking**: When applicants apply together for the same role, they tell the admins; an admin runs `/combine <position>, <name1>, <name2>, ...` in the admin chat. The bot assigns a shared `Group_ID` (UUID) to all listed applications for that role. Names are resolved from the Users sheet.
- **Display**: In election data, applicants with the same non-empty `Group_ID` are merged into one display entry: names appear on one line (e.g. "Name1, Name2") and one Fiirumi link is used if any. Implemented in `_applicants_for_role_enriched()` in **src/sheets_data_manager.py**.
- **Electing**: To mark a group as elected, the admin must list **all** members: `/elected <position>, <name1>, <name2>, ...`. If any member of the group is missing from the list, the bot returns an error asking to list all members. Implemented in `DataManager.set_applicants_elected()` and the `/elected` handler in **src/admin_commands.py**.
- **Data**: Applications sheet has a `Group_ID` column; status updates (including `group_id`) are queued and flushed with `status_update_queue`. No separate combining-info column.
