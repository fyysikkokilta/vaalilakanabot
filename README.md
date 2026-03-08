# Vaalilakanabot

A Telegram bot that maintains a listing of candidates during elections and announces new posts on the guild's Discourse-based discussion forum [Φrumi](https://fiirumi.fyysikkokilta.fi).

## Features

- **Registration**: Users register once with name, email, and consent (show on website's official page). Use `/register` (English) or `/rekisteroidy` (Finnish) in a private chat. Registration can be updated by running the command again.
- Guild members can apply for both elected and non-elected positions. **Applying requires prior registration**; the bot will prompt unregistered users to register first.
- **Admin approval**: Applications for elected positions (board and elected officials) require admin approval before being added to the election sheet.
- **Group applications**: Applicants can apply together for the same role. They tell the admins; an admin uses `/combine <position>, <name1>, <name2>, ...` to link them. Group members then appear on one line in the election sheet. When marking a group as elected, the admin must list all members: `/elected <position>, <name1>, <name2>, ...`.
- Announces in chats where the bot has been added whenever there's a new post on Fiirumi.
- The bot's admin user can maintain the electronic election sheet.
- Jauhis fun

## CI/CD Pipeline

This project uses GitHub Actions for continuous integration and deployment:

- **Automatic builds**: Docker images are automatically built and pushed to GitHub Container Registry on every push to main/master branch
- **Image tags**: Images are tagged with branch name, commit SHA, and semantic version tags
- **Registry**: Images are available at `ghcr.io/fyysikkokilta/vaalilakanabot`

### Development vs Production

- **Development**: Use `docker-compose up` (uses local build via override file)
- **Production**: Use `docker-compose -f docker-compose.prod.yml up` (uses pre-built image)

## Setup

- Install the project (dependencies are defined in `pyproject.toml`):  
  `pip install -e .`  
  For development with type checkers and linting:  
  `pip install -e ".[dev]"`
- Create a Telegram bot with Bot Father and save the bot token.
- Create a Discourse API key for the bot.
- Create an admin Telegram group and save its ID, for example using the `@RawDataBot`.
- Set up Google Sheets:
  - In Google Cloud Console, enable Google Sheets API and Google Drive API
  - Create a Service Account and download the JSON credentials
  - Save the credentials file at the project root as `google_credentials.json` (ignored by git)
  - Create a Google Sheets document and share it with the service account email (Editor permissions)
  - Set `GOOGLE_SHEET_URL` in `bot.env` to the full URL of your Google Sheet
- Create `bot.env` according to the example file `bot.env.example`.
- Initialize election structure in Google Sheets
- Run the bot: `vaalilakanabot` (or `python vaalilakanabot.py`)
- Add the bot to relevant discussion groups.

## Running the bot with Docker

- Create a Telegram bot and save the bot token.
- Create Discourse api keys to be used by the bot.
- Create an admin Telegram group and get the id of the group using, for example, `@RawDataBot`.
- **Optional**: Set `ELECTION_YEAR` in `bot.env` to automatically generate Discourse areas (see Automatic Area Generation below).
- **If not using automatic generation**: Manually create Discourse areas for the introductions and questions.
- Create the post for the Election sheet. The post should contain a separate empty message that will be edited by the bot.
- Create Google service account credentials with access to Google Sheets API for the bot to use and export the credentials as `google_credentials.json`.
- Create `bot.env` according to the example file `bot.env.example`.
- Run the bot to populate the Google Sheets document.
- Add the election sheet data to the generated Sheets. IDs are generated automatically so don't touch those!
- Start the jauhistelu.

### Docker Deployment Options

**Development (local build):**

```bash
docker-compose up
```

**Production (pre-built image):**

```bash
docker-compose -f docker-compose.prod.yml up
```

**Using the deployment script:**

```bash
./update-deployment.sh
```

## Commands

### User Commands

- `/start` - Register channel for announcements
- `/lakana` - Show current election sheet (Finnish)
- `/sheet` - Show current election sheet (English)
- `/hakemukset` - Show your applications (Finnish, private chat)
- `/applications` - Show your applications (English, private chat)
- **Registration (private chat):** You must register before applying.
  - `/start` - Register or update your info (English, also works as entry point)
  - `/rekisteroidy` - Register or update your info (Finnish)
  - `/register` - Register or update your info (English)
- **Applying (private chat):**
  - `/hae` - Start application form (Finnish)
  - `/apply` - Start application form (English)
- **Announcement channel management:**
  - `/ilmoitukset` - Register this chat for announcements (Finnish)
  - `/announcements` - Register this chat for announcements (English)
  - `/stop` - Unregister this chat from announcements
- `/apua` - Show help guide (Finnish)
- `/help` - Show help guide (English)

### Fun Commands

- `/jauhis` - Send jauhis sticker
- `/jauh` - Send jauh sticker
- `/jauho` - Send jauho sticker
- `/lauh` - Send lauh sticker
- `/mauh` - Send mauh sticker
- `/yauh` - Send yauh sticker

### Admin Commands (Admin Chat Only)

- `/remove <position>, <name>` - Remove applicant from position
- `/elected <position>, <name>` or `<position>, <name1>, <name2>, ...` - Mark as elected. **For group applications you must list all members** (e.g. `/elected Puheenjohtaja, Maija, Pekka`).
- `/combine <position>, <name1>, <name2>, ...` - Link applicants as a group (they appear on one line; use when applicants apply together).
- `/add_fiirumi <position>, <name>, <thread_id>` - Add Fiirumi link to applicant
- `/remove_fiirumi <position>, <name>` - Remove Fiirumi link from applicant
- `/export_officials_website` - Export officials data as CSV for Guild website (respects Users sheet consent)
- `/admin_help` - Show detailed admin commands help

**Note:**

- Admin commands support both Finnish and English division and role names
- If a name is not found, the bot will show available options
- All bot commands work seamlessly with manual Google Sheets editing
- Changes made directly in Google Sheets sync automatically with the bot

## Automatic Fiirumi Area Generation

The bot can automatically create the necessary Discourse categories for elections when started. This eliminates the need to manually create categories each year.

### How It Works

Set the `ELECTION_YEAR` environment variable in `bot.env` to the target election year:

```bash
ELECTION_YEAR=2025
```

When the bot starts and the current year matches `ELECTION_YEAR`, it will automatically create:

1. **Parent category**: `vaalipeli-{year}` (e.g., "Vaalipeli 2025")
2. **Subcategory**: `esittelyt` (Introductions) - for candidate introductions
3. **Subcategory**: `kysymykset` (Questions) - for questions to candidates
4. **Election sheet topic**: A topic titled "Vaalilakana {year}" in the parent category. The bot finds or creates this topic and updates it with the election sheet every 60 seconds.

The bot will check if categories already exist before creating them, so it's safe to run multiple times.

### Example URLs Generated

For `ELECTION_YEAR=2025`:

- Main (+ election sheet topic): `https://fiirumi.fyysikkokilta.fi/c/vaalipeli-2025`
- Introductions: `https://fiirumi.fyysikkokilta.fi/c/vaalipeli-2025/esittelyt`
- Questions: `https://fiirumi.fyysikkokilta.fi/c/vaalipeli-2025/kysymykset`

### Configuration

When `ELECTION_YEAR` is set to the current year, all Fiirumi URLs are derived automatically — introductions, questions, and the election sheet post URL. No additional URL configuration is required.

### Admin Approval

Applications for elected positions require admin approval:

1. When a user submits an application for an elected position, the bot sends an approval request to the admin chat.
2. The admin chat shows the application details and two buttons: "✅ Approve" and "❌ Reject".
3. When an admin approves the application:
   - The application is added to the election sheet
   - An approval notification is sent to the applicant
   - Channels receive a regular notification about the new name in the election sheet
4. When an admin rejects the application:
   - The application is removed from the pending list
   - A rejection notification is sent to the applicant
5. The user cannot submit a new application to the same position as long as the previous application is pending.

### Registration

1. In a **private chat** with the bot, use `/register` (English) or `/rekisteroidy` (Finnish).
2. Enter your full name, email, and whether your name may be shown on the guild website.
3. After registering, you can apply with `/apply` or `/hae`. Running `/register` or `/rekisteroidy` again updates your info.

### Group Applications

When several people apply together for the same role:

1. Each person applies normally (they must be registered). They tell the board they are applying as a group.
2. In the admin chat, an admin runs: `/combine <position>, <name1>, <name2>, ...` (all names for that role that form the group).
3. The bot links those applications with a shared Group_ID; they then appear on **one line** in the election sheet (e.g. "Name1, Name2").
4. When marking the group as elected, the admin must list **all** members: `/elected <position>, <name1>, <name2>, ...`. If any member is missing, the bot asks to list all members.

## Google Sheets Integration

The bot uses Google Sheets as the complete data storage solution for all bot data (election structure, applications, channels, forum posts, etc.), providing easier admin management and real-time collaboration.

### Benefits

- **Easy admin editing**: Admins can directly edit election data in Google Sheets
- **Real-time collaboration**: Multiple admins can work simultaneously
- **Data validation**: Built-in validation prevents common errors
- **Backup and history**: Google Sheets provides automatic version history
- **Better organization**: Clear separation between election structure and applications

### Setup Requirements

1. Google account with Google Sheets access
2. Google Cloud Project with Sheets API enabled
3. Service Account with appropriate permissions

### Google Sheets Structure

The bot creates and manages 4 worksheets in your Google Sheets document:

#### Sheet 1: "Election Structure"

| Column | Field       | Description                                      |
| ------ | ----------- | ------------------------------------------------ |
| A      | ID          | Unique role identifier (auto-generated)          |
| B      | Division_FI | Division name in Finnish                         |
| C      | Division_EN | Division name in English                         |
| D      | Role_FI     | Role name in Finnish                             |
| E      | Role_EN     | Role name in English                             |
| F      | Type        | Role type (BOARD, ELECTED, NON_ELECTED, AUDITOR) |
| G      | Amount      | Number of positions available                    |
| H      | Deadline    | Application deadline (dd.mm. format)             |

#### Sheet 2: "Applications"

| Column | Field        | Description                                                       |
| ------ | ------------ | ----------------------------------------------------------------- |
| A      | Timestamp    | When the application was submitted                                |
| B      | Role_ID      | Reference to role ID from Election Structure                      |
| C      | Telegram_ID  | User's Telegram ID (links to Users sheet for name/email)          |
| D      | Fiirumi_Post | Link to forum post                                                |
| E      | Status       | APPROVED, DENIED, REMOVED, ELECTED, or empty (pending)            |
| F      | Language     | Language of the application (fi/en)                               |
| G      | Group_ID     | Shared ID for group applications (same value = one line in sheet) |

#### Sheet 3: "Users"

| Column | Field                   | Description                                                    |
| ------ | ----------------------- | -------------------------------------------------------------- |
| A      | Telegram_ID             | User's Telegram ID                                             |
| B      | Name                    | Full name                                                      |
| C      | Email                   | Email address                                                  |
| D      | Telegram                | Telegram username                                              |
| E      | Show_On_Website_Consent | TRUE/FALSE – consent to show person on website's official page |
| F      | Updated_At              | Last update timestamp                                          |

Users register via `/register` or `/rekisteroidy`; applying uses this data. The single consent field controls whether the person is shown on the website's official page (used by `/export_officials_website`).

#### Sheet 4: "Channels"

| Column | Field      | Description                 |
| ------ | ---------- | --------------------------- |
| A      | Chat_ID    | Telegram chat ID            |
| B      | Added_Date | When channel was registered |

### Admin Workflow

**Adding New Roles:**

1. Open the Google Sheet
2. Go to "Election Structure" tab
3. Add a new row with division and role information
   3.1. Type is either BOARD, ELECTED, NON_ELECTED or AUDITOR
   3.2. Deadline should have the format xx.yy. exactly
   3.3 ID will be auto-generated

**Managing Applications:**

1. Go to "Applications" tab
2. Applications added via bot appear automatically
3. Edit applicant data directly: status, Fiirumi links, etc.
4. Use bot commands or direct editing for status changes
5. Status options: APPROVED, DENIED, REMOVED, ELECTED, or empty (pending)

### Election Sheet Preamble

The bot automatically updates the election sheet post on Discourse with the latest data from Google Sheets. You can add a preamble (introduction text, instructions, announcements) that will be preserved when the bot updates the sheet.

**How to add a preamble:**

1. Edit the election sheet post on Discourse
2. Add your preamble text at the top of the post
3. Add the marker line: `---SHEET STARTS HERE---`
4. The bot will preserve everything above the marker when updating

**Example:**

```
Welcome to the 2025 elections! Please review the candidates below.

Important dates:
- Voting starts: 15.3.
- Voting ends: 22.3.

---SHEET STARTS HERE---

[Bot-managed election sheet content appears here]
```

**Notes:**

- The election sheet post URL is set automatically when ELECTION_YEAR is configured.
- The preamble can contain any Markdown formatting
- The marker must be on its own line with no extra spaces
- If no marker is present, the entire post will be replaced (no preamble preserved)
- The bot updates the sheet automatically every 60 seconds

### Data Validation

The system includes built-in validation to prevent the role name consistency issues you were concerned about:

- Unique role IDs prevent string matching problems
- Real-time validation checks data as you type
- Duplicate detection highlights duplicate role names
- Consistency checks ensure role IDs match between sheets

For detailed setup instructions and troubleshooting, see the Google Sheets integration documentation.

## Additional Information

For more information about Telegram bots, you can read for example [Kvantti I/19 p.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf).

The bot was created by [Einari Tuukkanen](https://github.com/EinariTuukkanen) and Uula Ollila.
