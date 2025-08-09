"""Admin commands and operations."""

import logging
import re
from io import StringIO

from telegram import Update
from telegram.ext import ContextTypes

from .config import ADMIN_CHAT_ID
from .sheets_data_manager import DataManager
from .announcements import announce_to_channels
from .utils import create_fiirumi_link

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
        found_position = data_manager.find_role_by_name(position)
        if not found_position:
            # Show available positions
            all_positions = data_manager.get_all_roles()
            position_list = "\n".join(
                [f"• {pos['Role_FI']} / {pos['Role_EN']}" for pos in all_positions[:20]]
            )  # Limit to first 20
            await update.message.reply_text(
                f"Unknown position: {position}\n\n"
                f"Available positions (showing first 20):\n{position_list}"
            )
            return

        success = await data_manager.remove_applicant(found_position, name, context)
        if success:
            await update.message.reply_text(f"Removed:\n{found_position}: {name}")
        else:
            await update.message.reply_text(
                f"Failed to remove applicant: {name} from {found_position}. Check if the applicant exists for this position."
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
            f'Added Fiirumi:\n{found_position}: <a href="{fiirumi}">{name}</a>',
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
        found_position = data_manager.find_role_by_name(position)
        if not found_position:
            await update.message.reply_text(f"Unknown position: {position}")
            return

        data_manager.set_applicant_fiirumi(found_position, name, "")
        await update.message.reply_text(f"Fiirumi link removed:\n{name}")
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
        found_position = data_manager.find_role_by_name(position)
        if not found_position:
            await update.message.reply_text(f"Unknown position: {position}")
            return

        data_manager.set_applicant_elected(found_position, name)
        await update.message.reply_text(f"Applicant elected:\n{found_position}: {name}")

        # Find the user's Telegram ID to send them a notification
        role = data_manager.find_role_by_name(found_position)
        if role:
            applications = data_manager.sheets_manager.get_applications_for_role(
                role["ID"]
            )
            for app in applications:
                if app["Name"] == name:
                    user_id = app["Telegram_ID"]
                    language = app.get(
                        "Language", "en"
                    )  # Default to English if not specified

                    # Send notification to the elected user
                    try:
                        if language == "fi":
                            notification_text = (
                                f"🎉 <b>Onneksi olkoon!</b>\n\n"
                                f"Sinut on valittu virkaan <b>{found_position}</b>! "
                                f"Kiitos hakemuksestasi."
                            )
                        else:
                            notification_text = (
                                f"🎉 <b>Congratulations!</b>\n\n"
                                f"You have been elected to the position <b>{found_position}</b>! "
                                f"Thank you for your application."
                            )

                        await context.bot.send_message(
                            chat_id=user_id, text=notification_text, parse_mode="HTML"
                        )
                        logger.info(
                            "Election notification sent to user %s for position %s",
                            user_id,
                            found_position,
                        )
                    except Exception as e:
                        logger.error("Failed to notify elected user %s: %s", user_id, e)
                    break

            # Send announcement to channels for BOARD and ELECTED roles
            role_type = role.get("Type", "")
            if role_type in ("BOARD", "ELECTED"):
                await announce_to_channels(
                    f"🎉 <i>{name}</i> elected for <b>{found_position}</b>",
                    context,
                    data_manager,
                )
                logger.info(
                    "Election announcement sent to channels for %s: %s",
                    found_position,
                    name,
                )

        logger.info(
            "Applicant %s elected for position %s by admin", name, found_position
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
        for division_data in data_manager.vaalilakana_full.values():
            for role_title, role_data in division_data.get("roles", {}).items():
                if role_data.get("type") == "BOARD":
                    continue  # Skip board roles

                # Write division and role information
                output.write(
                    f'"{division_data.get("division", "")}","{division_data.get("division_en", "")}","{role_title}","{role_data.get("title_en", role_title)}"'
                )

                # Write applicant names (only elected)
                for applicant in role_data.get("applicants", []):
                    if applicant.get("status") == "ELECTED":
                        output.write(f',"{applicant["name"]}"')

                output.write("\n")

        output.seek(0)
        await update.message.reply_document(output, filename="officials.csv")
    except Exception as e:
        logger.error("Error in export_officials_csv: %s", e)
        await update.message.reply_text(
            "Error exporting officials data. Please try again."
        )
