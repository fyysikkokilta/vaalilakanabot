# Vaalilakanabot

A Telegram bot that maintains a listing of candidates during elections and announces new posts on the guild's Discourse-based discussion forum [Φrumi](https://fiirumi.fyysikkokilta.fi).

## Features

- Guild members can apply for both elected and non-elected positions.
- **Admin approval**: Applications for elected positions (board and elected officials) require admin approval before being added to the election sheet.
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

- Install the required libraries: `pip install -r requirements.txt`
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
- Initialize election structure in Google Sheets (optional - can be done manually or from forum post)
- `$ python vaalilakanabot.py`
- Add the bot to relevant discussion groups.

## Running the bot with Docker

- Create a Telegram bot and save the bot token.
- Create Discourse api keys to be used by the bot.
- Create an admin Telegram group and get the id of the group using, for example, `@RawDataBot`.
- **Set up Google Sheets** with election structure (see Google Sheets Structure below)
- Create `bot.env` according to the example file `bot.env.example`.

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
- `/stop` - Unregister channel from announcements
- `/lakana` - Show current election sheet (Finnish)
- `/sheet` - Show current election sheet (English)
- `/hakemukset` - Show your applications (Finnish)
- `/applications` - Show your applications (English)
- `/hae` - Start application form (Finnish, private chat only)
- `/apply` - Start application form (English, private chat only)
- `/apua` - Show help guide (Finnish)
- `/help` - Show help guide (English)

### Fun Commands

- `/jauhis` - Send jauhis sticker
- `/jauh` - Send jauh sticker
- `/jauho` - Send jauho sticker
- `/lauh` - Send lauh sticker
- `/mauh` - Send mauh sticker

### Admin Commands (Admin Chat Only)

- `/remove <position>, <name>` - Remove applicant from position
- `/elected <position>, <name>` - Mark applicant as elected
- `/add_fiirumi <position>, <name>, <thread_id>` - Add Fiirumi link to applicant
- `/remove_fiirumi <position>, <name>` - Remove Fiirumi link from applicant
- `/export_officials_website` - Export officials data as CSV for Guild website
- `/admin_help` - Show detailed admin commands help

**Note:**

- Admin commands support both Finnish and English division and role names
- If names are not found, the bot will show available options
- All bot commands work seamlessly with manual Google Sheets editing
- Changes made directly in Google Sheets sync automatically with the bot

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

The bot creates and manages 5 worksheets in your Google Sheets document:

#### Sheet 1: "Election Structure"

| Column | Field       | Description                                      |
| ------ | ----------- | ------------------------------------------------ |
| A      | ID          | Unique role identifier (auto-generated)          |
| B      | Division_FI | Division name in Finnish                         |
| C      | Division_EN | Division name in English                         |
| D      | Role_FI     | Role name in Finnish                             |
| E      | Role_EN     | Role name in English                             |
| F      | Type        | Role type (BOARD, ELECTED, NON-ELECTED, AUDITOR) |
| G      | Amount      | Number of positions available                    |
| H      | Deadline    | Application deadline (dd.mm. format)             |

#### Sheet 2: "Applications"

| Column | Field        | Description                                                    |
| ------ | ------------ | -------------------------------------------------------------- |
| A      | Role_ID      | Reference to role ID from Election Structure                   |
| B      | Telegram_ID  | User's Telegram ID                                             |
| C      | Name         | Applicant's name                                               |
| D      | Email        | Applicant's email                                              |
| E      | Telegram     | Telegram username                                              |
| F      | Fiirumi_Post | Link to forum post                                             |
| G      | Status       | "APPROVED", "DENIED", "REMOVED", "ELECTED", or empty (pending) |
| H      | Language     | Language of the application for later announcements            |

#### Sheet 3: "Channels"

| Column | Field      | Description                 |
| ------ | ---------- | --------------------------- |
| A      | Chat_ID    | Telegram chat ID            |
| B      | Added_Date | When channel was registered |

#### Sheet 4: "Fiirumi Posts"

| Column | Field      | Description       |
| ------ | ---------- | ----------------- |
| A      | Post_ID    | Forum post ID     |
| B      | User_ID    | Author's user ID  |
| C      | Post_Title | Title of the post |
| D      | Post_Date  | Publication date  |
| E      | Category   | Forum category    |
| F      | Topic_ID   | Related topic ID  |

#### Sheet 5: "Question Posts"

| Column | Field        | Description           |
| ------ | ------------ | --------------------- |
| A      | Post_ID      | Question post ID      |
| B      | Topic_ID     | Related topic ID      |
| C      | Posts_Count  | Number of responses   |
| D      | Last_Updated | Last update timestamp |

### Admin Workflow

**Adding New Roles:**

1. Open the Google Sheet
2. Go to "Election Structure" tab
3. Add a new row with division and role information
4. ID will be auto-generated

**Managing Applications:**

1. Go to "Applications" tab
2. Applications added via bot appear automatically
3. Edit applicant data directly: status, Fiirumi links, etc.
4. Use bot commands or direct editing for status changes
5. Status options: APPROVED, DENIED, REMOVED, ELECTED, or empty (pending)

**Monitoring Activity:**

1. Check "Channels" tab to see registered Telegram channels
2. View "Fiirumi Posts" to track forum activity
3. Monitor "Question Posts" for Q&A engagement
4. Review "Applications" tab and filter by Status column:
   - Empty = Pending applications awaiting approval
   - "APPROVED" = Approved applications shown on election sheet
   - "DENIED" = Rejected applications
   - "ELECTED" = Applicants marked as elected
   - "REMOVED" = Applicants removed from position

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
