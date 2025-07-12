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

- Install the `python-telegram-bot` library (version >=21) and other required libraries.
- Create a Telegram bot with Bot Father and save the bot token.
- Create a Discourse API key for the bot.
- Create an admin Telegram group and save its ID, for example using the `@RawDataBot`.
- Create the election sheet for Fiirumi.
  - The message containing the election sheet must not have any text other than the election sheet itself.
  - Division names must be written in ALL CAPS, and each line should contain only the Finnish and English translations separated by a `/`.
  - Role lines must follow the format:  
    `{Finnish name} / {English name} ({number of positions}) {application deadline (in the format xx.yy.)}`
    - Everything except the Finnish name is optional, but the order must be exactly as specified.
- Create `bot.env` according to the example file `bot.env.example`.
- `$ python vaalilakanabot.py`
- Add the bot to relevant discussion groups.

## Running the bot with Docker

- Create a Telegram bot and save the bot token.
- Create Discourse api keys to be used by the bot.
- Create an admin Telegram group and get the id of the group using, for example, `@RawDataBot`.
- Create the vaalilakana for Fiirumi.
  - The message containing the vaalilakana must not have any text other than the vaalilakana itself.
  - Division names must be written in ALL CAPS, and each line should contain only the Finnish and English translations separated by a `/`.
  - Role lines must follow the format:  
    `{Finnish name} / {English name} ({number of positions}) {application deadline (in the format xx.yy.)}`
    - Everything except the Finnish name is optional, but the order must be exactly as specified.
- Create `bot.env` according to the example file `bot.env.example`.
- Make sure the empty vaalilakana is already created when starting the bot so that the local json is populated.

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

The bot supports the following commands:

- `/start` Registers the group as the bot's announcement channel and the group receives notifications from the bot.
- `/lakana` Shows the current election candidate status (in Finnish).
- `/sheet` Shows the current election candidate status (in English).
- `/jauhis` Shows an election-themed image.
- `/jauh` Shows an election-themed image.
- `/jauho` Shows an election-themed image.
- `/lauh` Shows an election-themed image.
- `/mauh` Shows an election-themed image.
- `/hae` Starts filling out the application form in Finnish.
- `/apply` Starts filling out the application form in English.
- `/help` Shows the English help guide.
- `/apua` Shows the Finnish help guide.

The following commands are available in the admin chat:

- `/remove` Removes a candidate from the sheet. (also works for non-elected positions; candidates can be removed through the bot)
- `/add_fiirumi` Adds a candidate's Fiirumi post to the election sheet.
- `/remove_fiirumi` Removes a Fiirumi post that has been added to the election sheet.
- `/selected` Marks a candidate as selected for a position in the election sheet. (also works for non-elected positions)
- `/edit_or_add_new_role` Adds a new role or modifies an existing role in the election sheet.
- `/remove_role` Removes a role from the election sheet.
- `/export_data` Creates a CSV file from applicant data.
- `/export_officials_website` Creates a CSV for importing into the Guild's website.
- `/pending` Shows all pending applications that require admin approval.
- `/admin_help` Shows the admin commands help guide.

**Note:** Admin commands support both Finnish and English division and role names. If names are not found, the bot will show available options.

### Admin Approval

Applications for elected positions (defined in `BOARD` and `ELECTED_OFFICIALS` environment variables) require admin approval:

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

## Additional Information

For more information about Telegram bots, you can read for example [Kvantti I/19 p.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf).

The bot was created by [Einari Tuukkanen](https://github.com/EinariTuukkanen) and Uula Ollila.
