"""Admin commands and operations."""

import logging
import re
from io import StringIO

from telegram import Update
from telegram.ext import ContextTypes

from .config import ADMIN_CHAT_ID
from .sheets_data_manager import DataManager
from .announcements import announce_to_channels
from .utils import create_fiirumi_link, get_notification_text, get_role_name

logger = logging.getLogger("vaalilakanabot")


def parse_command_parameters(message_text: str, command: str) -> str:
    """
    Parse command parameters from message text, handling @botname mentions.

    Args:
        message_text: The full message text
        command: The command to extract parameters for (e.g., "/remove")

    Returns:
        The parameters string without the command and @botname
    """
    # Remove the command from the beginning
    text = message_text.replace(command, "", 1).strip()

    # Remove @botname if present (handles both @botname and @botname_bot formats)
    # This regex matches @ followed by any word characters and optional _bot suffix
    text = re.sub(r"@\w+(?:_bot)?\s*", "", text)

    return text.strip()


def is_admin_chat(chat_id: int) -> bool:
    """
    Check if the chat is the admin chat.

    Args:
        chat_id: The chat ID to check

    Returns:
        True if the chat is the admin chat, False otherwise
    """
    return str(chat_id) == str(ADMIN_CHAT_ID)


async def admin_help(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Show help information for admins in English."""
    try:
        if not is_admin_chat(update.message.chat.id):
            return

        help_text = """
🔧 <b>Vaalilakanabot - Admin Commands</b>

<b>Applicant Management:</b>
• /remove &lt;position&gt;, &lt;name&gt; - Remove applicant from position
• /elected &lt;position&gt;, &lt;name&gt; - Mark applicant as elected

<b>Fiirumi Link Management:</b>
• /add_fiirumi &lt;position&gt;, &lt;name&gt;, &lt;thread_id&gt; - Add Fiirumi link to applicant
• /remove_fiirumi &lt;position&gt;, &lt;name&gt; - Remove Fiirumi link from applicant

<b>Data Export:</b>
• /export_officials_website - Export officials data as CSV file for the Guild's website

<b>Manual Data Editing in Google Sheets:</b>
• <b>Election Structure</b> sheet: Add/edit roles, amounts, deadlines
• <b>Applications</b> sheet: Manage applicants, statuses, Fiirumi links
• <b>Role Management</b>: Add new rows to create roles, IDs auto-generate
• <b>Application Status</b>: APPROVED, DENIED, REMOVED, ELECTED, or empty (pending)
• <b>Data Types</b>: BOARD, ELECTED, NON-ELECTED, AUDITOR
• <b>Real-time updates</b>: Changes sync automatically with the bot

<b>Examples:</b>
• /remove Puheenjohtaja, Maija Meikäläinen
• /elected Varapuheenjohtaja, Pekka Päällikkö
• /add_fiirumi Puheenjohtaja, Maija Meikäläinen, 12345

<b>Important Notes:</b>
• All commands work only in admin chat
• Thread ID can be found in Fiirumi post URL
• Deadline format: DD.MM. (e.g., 15.12.)
• <b>Division and role names support both Finnish and English</b>
• If a name is not found, the bot will show available options
• Commands work with or without @botname mentions
• <b>Google Sheets provides version history and collaborative editing</b>
            """

        await update.message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


async def remove_applicant(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Remove an applicant from a position."""
    try:
        if not is_admin_chat(update.message.chat.id):
            return

        text = parse_command_parameters(update.message.text, "/remove")
        params = text.split(",")

        try:
            position = params[0].strip()
            name = params[1].strip()
        except Exception as e:
            await update.message.reply_text(
                "Invalid parameters - /remove <position>, <name>"
            )
            raise ValueError("Invalid parameters") from e

        # Find position by Finnish or English name
        role = data_manager.find_role_by_name(position)
        if not role:
            await update.message.reply_text(f"Unknown position: {position}")
            return

        success, app_data = data_manager.remove_applicant(role, name)
        if success and app_data:
            await update.message.reply_text(f"Removed:\n{role.get('Role_EN')}: {name}")

            # Send notification to the removed applicant
            try:
                user_language = app_data.get("Language", "en")
                notification_text = get_notification_text(
                    "removed",
                    get_role_name(role, user_language != "en"),
                    user_language,
                )

                await context.bot.send_message(
                    chat_id=app_data.get("Telegram_ID"),
                    text=notification_text,
                    parse_mode="HTML",
                )
                logger.info(
                    "Sent removal notification to user %s for position %s in %s",
                    app_data.get("Telegram_ID"),
                    role.get("Role_EN"),
                    user_language,
                )
            except Exception as e:
                logger.error(
                    "Failed to notify user %s about removal: %s",
                    app_data.get("Telegram_ID"),
                    e,
                )
        else:
            await update.message.reply_text(
                f"Failed to remove applicant: {name} from {role.get('Role_EN')}. Check if the applicant exists for this position."
            )
    except Exception as e:
        logger.error(e)


async def add_fiirumi_to_applicant(update: Update, data_manager: DataManager):
    """Add a fiirumi link to an applicant."""
    try:
        if not is_admin_chat(update.message.chat.id):
            return

        text = parse_command_parameters(update.message.text, "/add_fiirumi")
        params = text.split(",")

        try:
            position = params[0].strip()
            name = params[1].strip()
            thread_id = params[2].strip()
        except Exception as e:
            await update.message.reply_text(
                "Invalid parameters - /add_fiirumi <position>, <name>, <thread_id>",
            )
            raise ValueError("Invalid parameters") from e

        # Find position by Finnish or English name
        found_position = data_manager.find_role_by_name(position)
        if not found_position:
            await update.message.reply_text(f"Unknown position: {position}")
            return

        fiirumi = create_fiirumi_link(thread_id)
        data_manager.set_applicant_fiirumi(found_position, name, fiirumi)

        await update.message.reply_html(
            f'Added Fiirumi:\n{found_position.get("Role_EN")}: <a href="{fiirumi}">{name}</a>',
        )
    except Exception as e:
        logger.error(e)


async def unassociate_fiirumi(update: Update, data_manager: DataManager):
    """Remove fiirumi link from an applicant."""
    try:
        if not is_admin_chat(update.message.chat.id):
            return

        text = parse_command_parameters(update.message.text, "/remove_fiirumi")
        params = [arg.strip() for arg in text.split(",")]

        try:
            position, name = params
        except Exception as e:
            logger.error(e)
            await update.message.reply_text(
                "Invalid parameters - /remove_fiirumi <position>, <name>"
            )
            return

        # Find position by Finnish or English name
        role = data_manager.find_role_by_name(position)
        if not role:
            await update.message.reply_text(f"Unknown position: {position}")
            return

        data_manager.set_applicant_fiirumi(role, name, "")
        await update.message.reply_text(
            f"Fiirumi link removed:\n{role.get('Role_EN')}: {name}"
        )
    except Exception as e:
        logger.error(e)


async def add_elected_tag(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Mark an applicant as elected."""
    try:
        if not is_admin_chat(update.message.chat.id):
            return

        text = parse_command_parameters(update.message.text, "/elected")
        params = text.split(",")

        try:
            position = params[0].strip()
            name = params[1].strip()
        except Exception as e:
            await update.message.reply_text(
                "Invalid parameters - /elected <position>, <name>"
            )
            raise ValueError from e

        # Find position by Finnish or English name
        role = data_manager.find_role_by_name(position)
        if not role:
            await update.message.reply_text(f"Unknown position: {position}")
            return

        data_manager.set_applicant_elected(role, name)
        await update.message.reply_text(
            f"Applicant elected:\n{role.get('Role_EN')}: {name}"
        )

        # Find the user's Telegram ID to send them a notification
        if role:
            applications = data_manager.get_applications_for_role(role.get("ID"))
            for app in applications:
                if app.get("Name") == name:
                    user_id = app.get("Telegram_ID")
                    language = app.get("Language", "en")

                    # Send notification to the elected user
                    try:
                        notification_text = get_notification_text(
                            "elected",
                            get_role_name(role, language != "en"),
                            language,
                        )

                        await context.bot.send_message(
                            chat_id=user_id, text=notification_text, parse_mode="HTML"
                        )
                        logger.info(
                            "Election notification sent to user %s for position %s",
                            user_id,
                            role.get("Role_EN"),
                        )
                    except Exception as e:
                        logger.error("Failed to notify elected user %s: %s", user_id, e)
                    break

            # Send announcement to channels for BOARD and ELECTED roles
            role_type = role.get("Type")
            if role_type in ("BOARD", "ELECTED"):
                await announce_to_channels(
                    f"🎉 <i>{name}</i> elected for <b>{role.get("Role_EN")}</b>",
                    context,
                    data_manager,
                )
                logger.info(
                    "Election announcement sent to channels for %s: %s",
                    role.get("Role_EN"),
                    name,
                )

        logger.info(
            "Applicant %s elected for position %s by admin",
            name,
            role.get("Role_EN"),
        )

    except Exception as e:
        logger.error(e)


async def export_officials_website(update: Update, data_manager: DataManager):
    """Export officials data to CSV format compatible with the Guild website."""
    try:
        if not is_admin_chat(update.message.chat.id):
            return

        output = StringIO()

        # Process each role from the full dataset, filtering out board roles
        for division_data in data_manager.vaalilakana_full:
            for role_data in division_data.get("Roles", []):
                if role_data.get("Type") == "BOARD":
                    continue  # Skip board roles

                # Write division and role information
                division_fi = division_data.get("Division_FI")
                division_en = division_data.get("Division_EN")
                role_fi = role_data.get("Role_FI")
                role_en = role_data.get("Role_EN")
                output.write(f'"{division_fi}","{division_en}","{role_fi}","{role_en}"')

                # Write applicant names (only elected)
                for applicant in role_data.get("Applicants", []):
                    if applicant.get("Status") == "ELECTED":
                        output.write(f',"{applicant.get("Name")}"')

                output.write("\n")

        output.seek(0)
        await update.message.reply_document(output, filename="officials.csv")
    except Exception as e:
        logger.error("Error in export_officials_csv: %s", e)
        await update.message.reply_text(
            "Error exporting officials data. Please try again."
        )
