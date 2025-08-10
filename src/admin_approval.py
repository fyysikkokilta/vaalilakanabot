"""Admin approval functionality for applications."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .admin_commands import is_admin_chat
from .config import ADMIN_CHAT_ID
from .announcements import announce_to_channels
from .sheets_data_manager import DataManager
from .types import ApplicationRow
from .utils import get_notification_text, get_role_name

logger = logging.getLogger("vaalilakanabot")


async def send_admin_approval_request(
    context: ContextTypes.DEFAULT_TYPE,
    data_manager: DataManager,
    applicant: ApplicationRow,
):
    """Send an approval request to admin chat."""
    user_id = applicant.get("Telegram_ID")

    # Get division from role data
    role = data_manager.get_role_by_id(applicant.get("Role_ID", ""))
    division = role.get("Division_FI", "") if role else ""

    # Check if user already has other elected role applications
    existing_applications = data_manager.get_applications_for_user(user_id)

    elected_roles = []
    for application in existing_applications:
        other_role = data_manager.get_role_by_id(application.get("Role_ID", ""))
        if (
            other_role
            and other_role.get("Type") in ("BOARD", "ELECTED")
            and other_role.get("ID") != role.get("ID")
        ):
            elected_roles.append(other_role.get("Role_EN"))

    # Build the admin message
    text = (
        f"🗳️ <b>New application for elected position</b>\n\n"
        f"<b>Position:</b> {role.get('Role_EN')}\n"
        f"<b>Division:</b> {division}\n"
        f"<b>Name:</b> {applicant.get('Name')}\n"
        f"<b>Email:</b> {applicant.get('Email')}\n"
        f"<b>Telegram:</b> @{applicant.get('Telegram')}\n\n"
    )

    # Add warning if user has other elected applications
    if elected_roles:
        text += (
            "⚠️ <b>WARNING: Applicant has other elected position applications!</b>\n\n"
            "<b>Other applications:</b>\n"
        )
        for role in elected_roles:
            text += f"• {role}\n"

    text += "Approve application?"

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


async def handle_admin_approval(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Handle admin approval/rejection of applications."""
    query = update.callback_query
    await query.answer()

    # Check if this is from admin chat
    if not is_admin_chat(query.message.chat.id):
        await query.answer("This action is for admins only.", show_alert=True)
        return

    callback_data = query.data
    if not (
        callback_data.startswith("approve_") or callback_data.startswith("reject_")
    ):
        return

    action, application_ref = callback_data.split("_", 1)
    # application_ref is ROLE_ID_TELEGRAMID
    try:
        role_id, telegram_id_str = application_ref.rsplit("_", 1)
        telegram_id = int(telegram_id_str)
    except Exception:
        await query.edit_message_text("❌ Invalid approval reference.")
        return

    # Build a synthetic application from current data
    # Find role by id
    roles = data_manager.get_all_roles()
    role_row = next((r for r in roles if r.get("ID") == role_id), None)
    if not role_row:
        await query.edit_message_text("❌ Role not found for this application.")
        return

    # Get the applicant row
    user_apps = data_manager.get_applications_for_user(telegram_id)
    application = next(
        (
            a
            for a in user_apps
            if a.get("Role_ID") == role_id and a.get("Status", "PENDING") == "PENDING"
        ),
        None,
    )

    if not application:
        await query.edit_message_text("❌ Application not found or already processed.")
        return

    name = application.get("Name")
    user_id = telegram_id
    language = application.get("Language")

    if action == "approve":
        # Approve the application
        approved_app = data_manager.approve_application(role_id, telegram_id)
        if approved_app:
            await query.edit_message_text(
                f"✅ <b>Application approved!</b>\n\n"
                f"<b>Position:</b> {role_row.get("Role_EN")}\n"
                f"<b>Applicant:</b> {name}\n\n"
                f"Application has been added to the election sheet and notification sent to channels.",
                parse_mode="HTML",
            )

            # Notify the applicant
            try:
                notification_text = get_notification_text(
                    "approved",
                    get_role_name(role_row, language != "en"),
                    language,
                )

                await context.bot.send_message(
                    chat_id=user_id, text=notification_text, parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Failed to notify applicant %s: %s", user_id, e)

            # Announce to channels
            await announce_to_channels(
                f"<b>New candidate on election sheet!</b>\n{role_row.get('Role_EN')}: <i>{name}</i>",
                context,
                data_manager,
            )

            logger.info("Application %s approved by admin", application_ref)
        else:
            await query.edit_message_text("❌ Error approving application.")

    elif action == "reject":
        # Reject the application
        result = data_manager.reject_application(role_id, telegram_id)
        if result:
            await query.edit_message_text(
                f"❌ <b>Application rejected!</b>\n\n"
                f"<b>Position:</b> {role_row.get('Role_EN')}\n"
                f"<b>Applicant:</b> {name}\n\n"
                f"Application has been marked as DENIED.",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text("❌ Error rejecting application.")

        # Notify the applicant about rejection
        try:
            notification_text = get_notification_text(
                "rejected",
                get_role_name(role_row, language != "en"),
                language,
            )

            await context.bot.send_message(
                chat_id=user_id, text=notification_text, parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Failed to notify applicant %s: %s", user_id, e)

        logger.info("Application %s rejected by admin", application_ref)
