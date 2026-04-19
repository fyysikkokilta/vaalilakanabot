"""Admin commands and operations."""

import logging
import re
from io import BytesIO, StringIO
from typing import Dict, List, Optional, Tuple

from telegram import Message, Update
from telegram.ext import ContextTypes

from .config import ADMIN_CHAT_ID
from .sheets_data_manager import DataManager
from .types import (
    ApplicationRow,
    ConsentedApplicant,
    ElectionStructureRow,
    UserRow,
)
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
    text = message_text[len(command) :].strip()

    # Remove @botname if present (handles both @botname and @botname_bot formats)
    # This regex matches @ followed by any word characters and optional _bot suffix
    text = re.sub(r"^@\w+(?:_bot)?\s*", "", text)

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
• To <b>remove grouping</b>: clear the <code>Group_ID</code> cell(s) directly in the <b>Applications</b> sheet in Google Sheets. The applicants will then appear on separate lines again.

<b>Important Notes:</b>
• All commands work only in admin chat
• Thread ID can be found in Fiirumi post URL
• Deadline format: DD.MM. (e.g., 15.12.)
• <b>Division and role names support both Finnish and English</b>
• If a position or name is not found, the bot replies with an error — check the spelling against the Google Sheet
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

        result = await _parse_admin_role_names(
            message,
            data_manager,
            "/remove",
            1,
            "Invalid parameters - /remove <position>, <name>",
        )
        if not result:
            return
        role, names = result
        name = names[0]

        success, app_data = data_manager.remove_applicant(role, name)
        if success and app_data:
            await message.reply_text(f"Removed:\n{role.get('Role_EN')}: {name}")

            # Send notification to the removed applicant
            try:
                is_finnish = (app_data.get("Language") or "en") == "fi"
                notification_text = get_notification_text(
                    "removed",
                    get_role_name(role, is_finnish),
                    is_finnish,
                )

                telegram_id = app_data.get("Telegram_ID")
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=notification_text,
                    parse_mode="HTML",
                )
                logger.info(
                    "Sent removal notification to user %s for position %s",
                    app_data.get("Telegram_ID"),
                    role.get("Role_EN"),
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

        result = await _parse_admin_role_names(
            message,
            data_manager,
            "/add_fiirumi",
            2,
            "Invalid parameters - /add_fiirumi <position>, <name>, <thread_id>",
        )
        if not result:
            return
        found_position, names = result
        name, thread_id = names[0], names[1]

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

        result = await _parse_admin_role_names(
            message,
            data_manager,
            "/remove_fiirumi",
            1,
            "Invalid parameters - /remove_fiirumi <position>, <name>",
        )
        if not result:
            return
        role, names = result
        name = names[0]

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


async def _parse_admin_role_names(
    msg: Message,
    data_manager: DataManager,
    command: str,
    min_names: int,
    usage: str,
) -> Optional[Tuple[ElectionStructureRow, List[str]]]:
    """Parse '/cmd <position>, <name1>, ...' and resolve role.

    Returns (role, names) or None if validation failed (error already replied).
    """
    text = parse_command_parameters(msg.text or "", command)
    params = [p.strip() for p in text.split(",") if p.strip()]

    if len(params) < 1 + min_names:
        await msg.reply_text(usage)
        return None

    position = params[0]
    names = params[1:]

    role = data_manager.find_role_by_name(position)
    if not role:
        await msg.reply_text(f"Unknown position: {position}")
        return None

    return role, names


async def add_elected_tag(
    update: Update, _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Mark applicant(s) as elected. For group applications, list all members."""
    try:
        msg = update.message
        if msg is None or not is_admin_chat(msg.chat.id):
            return

        result = await _parse_admin_role_names(
            msg,
            data_manager,
            "/elected",
            1,
            "Usage: /elected <position>, <name> or /elected <position>, <name1>, <name2>, ... (for groups list all members)",
        )
        if not result:
            return
        role, names = result

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
    """Link applicants for a role as a group (same Group_ID)."""
    try:
        msg = update.message
        if msg is None or not is_admin_chat(msg.chat.id):
            return

        result = await _parse_admin_role_names(
            msg,
            data_manager,
            "/combine",
            2,
            "Usage: /combine <position>, <name1>, <name2>, ... (at least 2 names)",
        )
        if not result:
            return
        role, names = result

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
    role: ElectionStructureRow,
    consented_applicants: List[ConsentedApplicant],
) -> None:
    """Write one role row and its applicants to the CSV output."""
    output.write(
        f'"{role.get("Division_FI")}",'
        f'"{role.get("Division_EN")}",'
        f'"{role.get("Role_FI")}",'
        f'"{role.get("Role_EN")}"'
    )
    for applicant_data in consented_applicants:
        name = applicant_data["name"]
        telegram = applicant_data["telegram"]
        output.write(f',"{name}","{telegram}"' if telegram else f',"{name}"')
    output.write("\n")


def _consented_applicants_for_role_unmerged(
    elected_apps: List[ApplicationRow],
    role: ElectionStructureRow,
    users_by_id: Dict[int, UserRow],
) -> Tuple[List[ConsentedApplicant], int]:
    """Return (list of {name, telegram}, skipped_count) from elected applications.
    Applies consent per individual so group members without consent are excluded.
    """
    consented: List[ConsentedApplicant] = []
    skipped = 0
    for app in elected_apps:
        user = users_by_id.get(app.get("Telegram_ID"))
        if user is None:
            skipped += 1
            logger.debug(
                "Skipping elected user (no Users row) for role %s",
                role.get("Role_EN"),
            )
            continue
        if not user.get("Show_On_Website_Consent", False):
            skipped += 1
            logger.info(
                "Skipping official %s (role: %s) - no website consent",
                user.get("Name"),
                role.get("Role_EN"),
            )
            continue
        consented.append(
            {
                "name": str(user.get("Name", "") or ""),
                "telegram": user.get("Telegram", "") or None,
            }
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
        all_users = data_manager.get_all_users()
        users_by_id = {user.get("Telegram_ID"): user for user in all_users}
        # Bucket elected applications by Role_ID once (O(A)) instead of rescanning per role.
        elected_by_role: Dict[str, List[ApplicationRow]] = {}
        for app in data_manager.get_all_applications():
            if app.get("Status") != "ELECTED":
                continue
            rid = app.get("Role_ID")
            if rid:
                elected_by_role.setdefault(rid, []).append(app)
        skipped_count = 0

        for role in data_manager.get_all_roles():
            if role.get("Type") == "BOARD":
                continue
            elected_apps = elected_by_role.get(role.get("ID", ""), [])
            if not elected_apps:
                continue
            consented_applicants, skipped = _consented_applicants_for_role_unmerged(
                elected_apps, role, users_by_id
            )
            skipped_count += skipped
            if not consented_applicants:
                continue
            _write_officials_role_row(output, role, consented_applicants)

        output.seek(0)
        csv_content = output.getvalue()
        csv_bytes = BytesIO(csv_content.encode("utf-8"))

        if not csv_content.strip():
            await message.reply_text(
                "There are no officials to export. Either no one has been marked as "
                "elected with consent to show on the website, or no elected officials "
                "have given consent on the Users sheet."
            )
            return

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
