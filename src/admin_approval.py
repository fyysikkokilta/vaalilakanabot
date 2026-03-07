"""Admin approval functionality for applications."""

import logging
from typing import Dict, List, Literal, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .admin_commands import is_admin_chat
from .config import ADMIN_CHAT_ID
from .announcements import announce_to_channels
from .sheets_data_manager import DataManager
from .types import ApplicationRow, ElectionStructureRow
from .utils import get_notification_text, get_role_name

logger = logging.getLogger("vaalilakanabot")


def _other_elected_roles(
    data_manager: DataManager, user_id: int, current_role_id: str
) -> List[str]:
    """Return list of other elected role names the user has applied for."""
    existing = data_manager.get_applications_for_user(user_id)
    out = []
    for app in existing:
        other = data_manager.get_role_by_id(app.get("Role_ID", ""))
        if (
            other
            and other.get("Type") in ("BOARD", "ELECTED")
            and other.get("ID") != current_role_id
        ):
            out.append(other.get("Role_EN") or "")
    return out


def _approval_message_text(
    role: Optional[ElectionStructureRow],
    division: str,
    display: Dict[str, str],
    elected_roles: List[str],
) -> str:
    """Build the approval request message body."""
    role_en = role.get("Role_EN", "") if role else ""
    telegram_handle_raw = (display.get("Telegram", "") or "").strip()
    if not telegram_handle_raw or telegram_handle_raw.lower() == "(none)":
        telegram_handle = "—"
    elif telegram_handle_raw.startswith("@"):
        telegram_handle = telegram_handle_raw
    else:
        telegram_handle = f"@{telegram_handle_raw}"
    text = (
        f"🗳️ <b>New application for elected position</b>\n\n"
        f"<b>Position:</b> {role_en}\n"
        f"<b>Division:</b> {division}\n"
        f"<b>Name:</b> {display.get('Name', '')}\n"
        f"<b>Email:</b> {display.get('Email', '')}\n"
        f"<b>Telegram:</b> {telegram_handle}\n\n"
    )
    if elected_roles:
        text += (
            "⚠️ <b>WARNING: Applicant has other elected position applications!</b>\n\n"
            "<b>Other applications:</b>\n"
        )
        for r in elected_roles:
            text += f"• {r}\n"
    text += "Approve application?"
    return text


async def send_admin_approval_request(
    context: ContextTypes.DEFAULT_TYPE,
    data_manager: DataManager,
    applicant: ApplicationRow,
) -> None:
    """Send an approval request to admin chat."""
    role = data_manager.get_role_by_id(applicant.get("Role_ID", ""))
    division = role.get("Division_FI", "") if role else ""
    elected_roles = _other_elected_roles(
        data_manager,
        applicant.get("Telegram_ID"),
        role.get("ID", "") if role else "",
    )
    display_user = data_manager.get_applicant_display(applicant)
    users_by_id = {applicant.get("Telegram_ID"): display_user} if display_user else {}
    display_names = data_manager.get_applicant_display_names_for_announcement(
        applicant.get("Role_ID", ""), applicant, users_by_id=users_by_id
    )
    display: Dict[str, str] = {
        "Name": display_names,
        "Email": display_user.get("Email", "") if display_user else "",
        "Telegram": display_user.get("Telegram", "") if display_user else "",
    }
    text = _approval_message_text(role, division, display, elected_roles)
    role_ref = f"{applicant.get('Role_ID')}_{applicant.get('Telegram_ID')}"

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{role_ref}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{role_ref}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        logger.info(
            "Admin approval request sent for application %s",
            role_ref,
        )
    except Exception as e:
        logger.error("Failed to send admin approval request: %s", e)


def _parse_approval_ref(
    callback_data: str,
) -> Optional[Tuple[str, str, int]]:
    """Parse callback_data into (action, role_id, telegram_id). Returns None if invalid."""
    if not (
        callback_data.startswith("approve_") or callback_data.startswith("reject_")
    ):
        return None
    action, ref = callback_data.split("_", 1)
    try:
        role_id, telegram_id_str = ref.rsplit("_", 1)
        telegram_id = int(str(telegram_id_str).replace("−", "-"))
        return (action, role_id, telegram_id)
    except Exception:
        return None


async def _notify_applicant(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    role_row: ElectionStructureRow,
    is_finnish: bool,
    kind: Literal["approved", "rejected"],
) -> None:
    """Send approval or rejection notification to the applicant."""
    try:
        text = get_notification_text(
            kind,
            get_role_name(role_row, is_finnish),
            is_finnish,
        )
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error("Failed to notify applicant %s: %s", user_id, e)


def _resolve_approval_context(
    data_manager: DataManager, role_id: str, telegram_id: int
) -> Tuple[Optional[ElectionStructureRow], Optional[ApplicationRow]]:
    """Return (role_row, application) or (None, None) if not found."""
    role_row = data_manager.get_role_by_id(role_id)
    if not role_row:
        return None, None
    user_apps = data_manager.get_applications_for_user(telegram_id)
    application = next(
        (
            a
            for a in user_apps
            if a.get("Role_ID") == role_id
            and (a.get("Status") or "").strip() in ("", "PENDING")
        ),
        None,
    )
    if not application:
        return None, None
    return role_row, application


async def handle_admin_approval(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Handle admin approval/rejection of applications."""
    query = update.callback_query
    if not query:
        return
    if not query.message or not is_admin_chat(query.message.chat.id):
        await query.answer("This action is for admins only.", show_alert=True)
        return
    await query.answer()

    parsed = _parse_approval_ref(query.data or "")
    if not parsed:
        await query.edit_message_text("❌ Invalid approval reference.")
        return
    action, role_id, telegram_id = parsed

    role_row, application = _resolve_approval_context(
        data_manager, role_id, telegram_id
    )
    if not role_row:
        await query.edit_message_text("❌ Role not found for this application.")
        return
    if not application:
        await query.edit_message_text("❌ Application not found or already processed.")
        return

    # For groups, show all names in announcements and messages
    display_names = data_manager.get_applicant_display_names_for_announcement(
        role_id, application
    )
    application_ref = f"{role_id}_{telegram_id}"
    is_finnish = (application.get("Language") or "").strip().lower() == "fi"

    if action == "approve":
        approved_app = data_manager.approve_application(role_id, telegram_id)
        if approved_app:
            await query.edit_message_text(
                f"✅ <b>Application approved!</b>\n\n"
                f"<b>Position:</b> {role_row.get('Role_EN')}\n"
                f"<b>Applicant(s):</b> {display_names}\n\n"
                f"Application has been added to the election sheet and notification sent to channels.",
                parse_mode="HTML",
            )
            await _notify_applicant(
                context, telegram_id, role_row, is_finnish, "approved"
            )
            await announce_to_channels(
                f"<b>Uusi nimi vaalilakanassa!</b>\n"
                f"<b>New candidate on the election sheet!</b>\n"
                f"<b>{role_row.get('Role_FI')} / {role_row.get('Role_EN')}:</b>\n"
                f"<i>{display_names}</i>",
                context,
                data_manager,
            )
            logger.info("Application %s approved by admin", application_ref)
        else:
            await query.edit_message_text("❌ Error approving application.")
    else:
        result = data_manager.reject_application(role_id, telegram_id)
        if result:
            await query.edit_message_text(
                f"❌ <b>Application rejected!</b>\n\n"
                f"<b>Position:</b> {role_row.get('Role_EN')}\n"
                f"<b>Applicant(s):</b> {display_names}\n\n"
                f"Application has been marked as DENIED.",
                parse_mode="HTML",
            )
            await _notify_applicant(context, telegram_id, role_row, is_finnish, "rejected")
            logger.info("Application %s rejected by admin", application_ref)
        else:
            await query.edit_message_text("❌ Error rejecting application.")
