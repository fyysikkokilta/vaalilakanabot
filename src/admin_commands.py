"""Admin commands and operations."""

import logging
import re
from io import BytesIO, StringIO
from typing import Dict, List, Literal, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from .config import ADMIN_CHAT_ID
from .sheets_data_manager import DataManager
from .types import ConsentedApplicant, DivisionData, RoleData, UserRow
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


async def admin_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information for admins in English."""
    try:
        if not update.message or not is_admin_chat(update.message.chat.id):
            return

        help_text = """
🔧 <b>Vaalilakanabot - Admin Commands</b>

<b>Applicant Management:</b>
• /remove &lt;position&gt;, &lt;name&gt; - Remove applicant from position
• /elected &lt;position&gt;, &lt;name&gt; or &lt;name1&gt;, &lt;name2&gt;, ... - Mark as elected (for groups, list all members)
• /combine &lt;position&gt;, &lt;name1&gt;, &lt;name2&gt;, ... - Link applicants as a group (same Group_ID)

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
• <b>Data Types</b>: BOARD, ELECTED, NON_ELECTED, AUDITOR
• <b>Real-time updates</b>: Changes sync automatically with the bot

<b>Examples:</b>
• /remove Puheenjohtaja, Maija Meikäläinen
• /elected Varapuheenjohtaja, Pekka Päällikkö (or for group: /elected Role, Name1, Name2)
• /combine Puheenjohtaja, Maija Meikäläinen, Pekka Päällikkö
• /add_fiirumi Puheenjohtaja, Maija Meikäläinen, 12345

<b>Group applications:</b>
• When applicants apply together: use /combine with all names for that role. They will appear on one line.
• When electing a group: use /elected with <b>all</b> members listed (e.g. /elected Role, Name1, Name2). The bot will reject if any group member is missing.

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
) -> None:
    """Remove an applicant from a position."""
    try:
        message = update.message
        if message is None or not is_admin_chat(message.chat.id):
            return

        text = parse_command_parameters(message.text or "", "/remove")
        params = text.split(",")

        try:
            position = params[0].strip()
            name = params[1].strip()
        except Exception as e:
            await message.reply_text("Invalid parameters - /remove <position>, <name>")
            raise ValueError("Invalid parameters") from e

        # Find position by Finnish or English name
        role = data_manager.find_role_by_name(position)
        if not role:
            await message.reply_text(f"Unknown position: {position}")
            return

        success, app_data = data_manager.remove_applicant(role, name)
        if success and app_data:
            await message.reply_text(f"Removed:\n{role.get('Role_EN')}: {name}")

            # Send notification to the removed applicant
            try:
                user_language: Literal["fi", "en"] = app_data.get("Language") or "en"
                notification_text = get_notification_text(
                    "removed",
                    get_role_name(role, user_language != "en"),
                    user_language,
                )

                telegram_id = app_data.get("Telegram_ID")
                await context.bot.send_message(
                    chat_id=telegram_id,
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
            await message.reply_text(
                f"Failed to remove applicant: {name} from {role.get('Role_EN')}. Check if the applicant exists for this position."
            )
    except Exception as e:
        logger.error(e)


async def add_fiirumi_to_applicant(update: Update, data_manager: DataManager) -> None:
    """Add a fiirumi link to an applicant."""
    try:
        message = update.message
        if message is None or not is_admin_chat(message.chat.id):
            return

        text = parse_command_parameters(message.text or "", "/add_fiirumi")
        params = text.split(",")

        try:
            position = params[0].strip()
            name = params[1].strip()
            thread_id = params[2].strip()
        except Exception as e:
            await message.reply_text(
                "Invalid parameters - /add_fiirumi <position>, <name>, <thread_id>",
            )
            raise ValueError("Invalid parameters") from e

        # Find position by Finnish or English name
        found_position = data_manager.find_role_by_name(position)
        if not found_position:
            await message.reply_text(f"Unknown position: {position}")
            return

        fiirumi = create_fiirumi_link(thread_id)
        success = data_manager.set_applicant_fiirumi(found_position, name, fiirumi)
        if not success:
            await message.reply_text(f"Applicant not found: {name}")
            return
        display_names = data_manager.get_applicant_display_names_for_role_and_name(
            found_position, name
        )
        await message.reply_html(
            f'Added Fiirumi:\n{found_position.get("Role_EN")}: <a href="{fiirumi}">{display_names}</a>',
        )
    except Exception as e:
        logger.error(e)


async def unassociate_fiirumi(update: Update, data_manager: DataManager) -> None:
    """Remove fiirumi link from an applicant."""
    try:
        message = update.message
        if message is None or not is_admin_chat(message.chat.id):
            return

        text = parse_command_parameters(message.text or "", "/remove_fiirumi")
        params = [arg.strip() for arg in text.split(",")]

        try:
            position, name = params
        except Exception as e:
            logger.error(e)
            await message.reply_text(
                "Invalid parameters - /remove_fiirumi <position>, <name>"
            )
            return

        # Find position by Finnish or English name
        role = data_manager.find_role_by_name(position)
        if not role:
            await message.reply_text(f"Unknown position: {position}")
            return

        success = data_manager.set_applicant_fiirumi(role, name, "")
        if not success:
            await message.reply_text(f"Applicant not found: {name}")
            return
        display_names = data_manager.get_applicant_display_names_for_role_and_name(
            role, name
        )
        await message.reply_text(
            f"Fiirumi link removed:\n{role.get('Role_EN')}: {display_names}"
        )
    except Exception as e:
        logger.error(e)


async def add_elected_tag(
    update: Update, _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Mark applicant(s) as elected. For group applications, list all members: /elected <position>, <name1>, <name2>, ..."""
    try:
        msg = update.message
        if msg is None or not is_admin_chat(msg.chat.id):
            return

        text = parse_command_parameters(msg.text or "", "/elected")
        params = [p.strip() for p in text.split(",") if p.strip()]

        if len(params) < 2:
            await msg.reply_text(
                "Usage: /elected <position>, <name> or /elected <position>, <name1>, <name2>, ... (for groups list all members)"
            )
            return

        position = params[0]
        names = params[1:]

        role = data_manager.find_role_by_name(position)
        if not role:
            await msg.reply_text(f"Unknown position: {position}")
            return

        success, reply_text = data_manager.set_applicants_elected(role, names)
        await msg.reply_text(reply_text)

        if success:
            logger.info(
                "Applicant(s) %s elected for position %s by admin",
                ", ".join(names),
                role.get("Role_EN"),
            )
    except Exception as e:
        logger.error(e)


async def combine_applicants(
    update: Update, _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Link applicants for a role as a group (same Group_ID). Usage: /combine <position>, <name1>, <name2>, ..."""
    try:
        msg = update.message
        if msg is None or not is_admin_chat(msg.chat.id):
            return

        text = parse_command_parameters(msg.text or "", "/combine")
        params = [p.strip() for p in text.split(",") if p.strip()]

        if len(params) < 3:
            await msg.reply_text(
                "Usage: /combine <position>, <name1>, <name2>, ... (at least 2 names)"
            )
            return

        position = params[0]
        names = params[1:]

        role = data_manager.find_role_by_name(position)
        if not role:
            await msg.reply_text(f"Unknown position: {position}")
            return

        success, reply_text = data_manager.combine_applicants(role, names)
        await msg.reply_text(reply_text)

        if success:
            logger.info(
                "Applicants %s combined for position %s by admin",
                ", ".join(names),
                role.get("Role_EN"),
            )
    except Exception as e:
        logger.error(e)


def _write_officials_role_row(
    output: StringIO,
    division_data: DivisionData,
    role_data: RoleData,
    consented_applicants: List[ConsentedApplicant],
) -> None:
    """Write one division/role row and its applicants to the CSV output."""
    output.write(
        f'"{division_data.get("Division_FI")}",'
        f'"{division_data.get("Division_EN")}",'
        f'"{role_data.get("Role_FI")}",'
        f'"{role_data.get("Role_EN")}"'
    )
    for applicant_data in consented_applicants:
        name = applicant_data["name"]
        telegram = applicant_data["telegram"]
        output.write(f',"{name}","{telegram}"' if telegram else f',"{name}"')
    output.write("\n")


def _consented_applicants_for_role(
    role_data: RoleData, users_by_id: Dict[int, UserRow]
) -> Tuple[List[ConsentedApplicant], int]:
    """Return (list of {name, telegram}, skipped_count) for elected applicants with consent."""
    consented: List[ConsentedApplicant] = []
    skipped = 0
    for applicant in role_data.get("Applicants", []):
        if applicant.get("Status") != "ELECTED":
            continue
        telegram_id = applicant.get("Telegram_ID")
        user = users_by_id.get(telegram_id)
        applicant_name = str(applicant.get("Name") or "")
        if user is None:
            consented.append({"name": applicant_name, "telegram": None})
        elif user.get("Show_On_Website_Consent", False):
            consented.append(
                {
                    "name": applicant_name,
                    "telegram": user.get("Telegram", "") or None,
                }
            )
        else:
            skipped += 1
            logger.info(
                "Skipping official %s (role: %s) - no website consent",
                applicant.get("Name"),
                role_data.get("Role_EN"),
            )
    return consented, skipped


async def export_officials_website(update: Update, data_manager: DataManager) -> None:
    """Export officials data to CSV format compatible with the Guild website.

    Respects user consent from the Users sheet: only includes users who have
    given Show_On_Website_Consent (show on the website's official page).
    When consented, exports name and Telegram handle.
    """
    try:
        message = update.message
        if message is None or not is_admin_chat(message.chat.id):
            return

        output = StringIO()
        all_users = data_manager.sheets_manager.get_all_users()
        users_by_id = {user.get("Telegram_ID"): user for user in all_users}
        skipped_count = 0

        for division_data in data_manager.vaalilakana_full:
            for role_data in division_data.get("Roles", []):
                if role_data.get("Type") == "BOARD":
                    continue
                consented_applicants, skipped = _consented_applicants_for_role(
                    role_data, users_by_id
                )
                skipped_count += skipped
                if not consented_applicants:
                    continue
                _write_officials_role_row(
                    output, division_data, role_data, consented_applicants
                )

        output.seek(0)
        csv_bytes = BytesIO(output.getvalue().encode("utf-8"))

        # Add info message about consent filtering
        info_msg = "Officials data exported successfully."
        if skipped_count > 0:
            info_msg += (
                f"\n\nℹ️ Note: {skipped_count} elected official(s) were excluded "
                "because they haven't given consent to be shown on the website's "
                "official page."
            )

        await message.reply_text(info_msg)
        await message.reply_document(document=csv_bytes, filename="officials.csv")

    except Exception as e:
        logger.error("Error in export_officials_csv: %s", e)
        if update.message is not None:
            await update.message.reply_text(
                "Error exporting officials data. Please try again."
            )
