"""Admin approval functionality for applications."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .admin_commands import is_admin_chat
from .config import ADMIN_CHAT_ID
from .announcements import announce_to_channels
from .sheets_data_manager import DataManager

logger = logging.getLogger("vaalilakanabot")


async def send_admin_approval_request(
    context: ContextTypes.DEFAULT_TYPE,
    data_manager: DataManager,
    application_ref: str,
    application_data: dict,
):
    """Send an approval request to admin chat."""
    applicant = application_data["applicant"]
    position = application_data["position"]
    division = application_data["division"]
    user_id = applicant["user_id"]

    # Check if user already has other elected role applications
    existing_elected_applications = []

    # Check for approved applications to elected roles (based on role Type)
    for role_title, role_data in data_manager.vaalilakana.items():
        if role_title != position and role_data.get("type") in ("BOARD", "ELECTED"):
            for app in role_data.get("applicants", []):
                if app["user_id"] == user_id and app.get("status") == "APPROVED":
                    existing_elected_applications.append(f"✅ {role_title} (approved)")

    # Check for pending applications to elected roles using Applications sheet rows
    # Build current role id for comparison
    current_role = data_manager.find_role_by_name(position)
    current_role_id = current_role.get("ID") if current_role else None

    for app_row in data_manager.pending_applications:
        # Pending = Status is empty (handled in getter). Match same user
        if int(app_row.get("Telegram_ID", 0)) != int(user_id):
            continue

        role_id = app_row.get("Role_ID", "")
        if not role_id or (current_role_id and role_id == current_role_id):
            continue

        # Resolve role by ID
        role_row = next(
            (r for r in data_manager.get_all_roles() if r.get("ID") == role_id),
            None,
        )
        if role_row and role_row.get("Type") in ("BOARD", "ELECTED"):
            role_title = role_row.get("Role_FI", role_id)
            existing_elected_applications.append(f"⏳ {role_title} (pending)")

    # Build the admin message
    text = (
        f"🗳️ <b>New application for elected position</b>\n\n"
        f"<b>Position:</b> {position}\n"
        f"<b>Division:</b> {division}\n"
        f"<b>Name:</b> {applicant['name']}\n"
        f"<b>Email:</b> {applicant['email']}\n"
        f"<b>Telegram:</b> @{applicant['telegram']}\n\n"
    )

    # Add warning if user has other elected applications
    if existing_elected_applications:
        text += (
            "⚠️ <b>WARNING: Applicant has other elected position applications!</b>\n\n"
            "<b>Other applications:</b>\n"
        )
        for app in existing_elected_applications:
            text += f"• {app}\n"

    text += "Approve application?"

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Approve", callback_data=f"approve_{application_ref}"
            ),
            InlineKeyboardButton(
                "❌ Reject", callback_data=f"reject_{application_ref}"
            ),
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
        logger.info("Admin approval request sent for application %s", application_ref)
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
    user_apps = data_manager.sheets_manager.get_applications_for_user(telegram_id)
    application = next(
        (
            a
            for a in user_apps
            if a.get("Role_ID") == role_id and a.get("Status", "") == ""
        ),
        None,
    )

    if not application:
        await query.edit_message_text("❌ Application not found or already processed.")
        return

    applicant = {
        "name": application.get("Name", ""),
        "email": application.get("Email", ""),
        "telegram": application.get("Telegram", ""),
        "user_id": telegram_id,
    }
    position = role_row.get("Role_FI", "")
    user_id = telegram_id
    language = application.get("Language", "en")

    if action == "approve":
        # Approve the application
        approved_app = data_manager.approve_application(role_id, telegram_id)
        if approved_app:
            await query.edit_message_text(
                f"✅ <b>Application approved!</b>\n\n"
                f"<b>Position:</b> {position}\n"
                f"<b>Applicant:</b> {applicant['name']}\n\n"
                f"Application has been added to the election sheet and notification sent to channels.",
                parse_mode="HTML",
            )

            # Notify the applicant
            try:
                if language == "fi":
                    notification_text = (
                        f"✅ <b>Hakemuksesi on hyväksytty!</b>\n\n"
                        f"Hakemuksesi virkaan <b>{position}</b> on hyväksytty ja lisätty vaalilakanaan. "
                        f"Kiitos hakemuksestasi!"
                    )
                else:
                    notification_text = (
                        f"✅ <b>Your application has been approved!</b>\n\n"
                        f"Your application for the position <b>{position}</b> has been approved and added to the election sheet. "
                        f"Thank you for your application!"
                    )

                await context.bot.send_message(
                    chat_id=user_id, text=notification_text, parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Failed to notify applicant %s: %s", user_id, e)

            # Announce to channels
            await announce_to_channels(
                f"<b>New candidate on election sheet!</b>\n{position}: <i>{applicant['name']}</i>",
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
                f"<b>Position:</b> {position}\n"
                f"<b>Applicant:</b> {applicant['name']}\n\n"
                f"Application has been marked as DENIED.",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text("❌ Error rejecting application.")

        # Notify the applicant about rejection
        try:
            if language == "fi":
                notification_text = (
                    f"❌ <b>Hakemuksesi on hylätty</b>\n\n"
                    f"Valitettavasti hakemuksesi virkaan <b>{position}</b> on hylätty. "
                    f"Voit ottaa yhteyttä admineihin lisätietojen saamiseksi."
                )
            else:
                notification_text = (
                    f"❌ <b>Your application has been rejected</b>\n\n"
                    f"Unfortunately, your application for the position <b>{position}</b> has been rejected. "
                    f"You can contact the admins for more information."
                )

            await context.bot.send_message(
                chat_id=user_id, text=notification_text, parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Failed to notify applicant %s: %s", user_id, e)

        logger.info("Application %s rejected by admin", application_ref)
