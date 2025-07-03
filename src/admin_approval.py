"""Admin approval functionality for applications."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .admin_commands import is_admin_chat
from .config import ADMIN_CHAT_ID, BOARD, ELECTED_OFFICIALS
from .announcements import announce_to_channels

logger = logging.getLogger("vaalilakanabot")


async def send_admin_approval_request(
    context: ContextTypes.DEFAULT_TYPE,
    data_manager,
    application_id: str,
    application_data: dict,
):
    """Send an approval request to admin chat."""
    applicant = application_data["applicant"]
    position = application_data["position"]
    division = application_data["division"]
    user_id = applicant["user_id"]

    # Check if user already has other elected role applications
    existing_elected_applications = []

    # Check for approved applications to elected roles
    for div_name, div_data in data_manager.vaalilakana.items():
        for role_title, role_data in div_data["roles"].items():
            if role_title in BOARD + ELECTED_OFFICIALS and role_title != position:
                for app in role_data["applicants"]:
                    if app["user_id"] == user_id:
                        existing_elected_applications.append(
                            f"✅ {role_title} (approved)"
                        )

    # Check for pending applications to elected roles
    for app_id, app_data in data_manager.pending_applications.items():
        if (
            app_data["applicant"]["user_id"] == user_id
            and app_data["position"] in BOARD + ELECTED_OFFICIALS
            and app_data["position"] != position
        ):
            existing_elected_applications.append(f"⏳ {app_data['position']} (pending)")

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
            f"⚠️ <b>WARNING: Applicant has other elected position applications!</b>\n\n"
            f"<b>Other applications:</b>\n"
        )
        for app in existing_elected_applications:
            text += f"• {app}\n"

    text += f"Approve application?"

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Approve", callback_data=f"approve_{application_id}"
            ),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{application_id}"),
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
        logger.info(f"Admin approval request sent for application {application_id}")
    except Exception as e:
        logger.error(f"Failed to send admin approval request: {e}")


async def handle_admin_approval(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
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

    action, application_id = callback_data.split("_", 1)
    application = data_manager.get_pending_application(application_id)

    if not application:
        await query.edit_message_text("❌ Application not found or already processed.")
        return

    applicant = application["applicant"]
    position = application["position"]
    user_id = applicant["user_id"]
    language = application.get("language", "fi")

    if action == "approve":
        # Approve the application
        approved_app = data_manager.approve_application(application_id)
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
                logger.error(f"Failed to notify applicant {user_id}: {e}")

            # Announce to channels
            await announce_to_channels(
                f"<b>Uusi nimi vaalilakanassa!</b>\n{position}: <i>{applicant['name']}</i>",
                context,
                data_manager,
            )

            logger.info(f"Application {application_id} approved by admin")
        else:
            await query.edit_message_text("❌ Error approving application.")

    elif action == "reject":
        # Reject the application
        data_manager.remove_pending_application(application_id)
        await query.edit_message_text(
            f"❌ <b>Application rejected!</b>\n\n"
            f"<b>Position:</b> {position}\n"
            f"<b>Applicant:</b> {applicant['name']}\n\n"
            f"Application has been rejected and will not be added to the election sheet.",
            parse_mode="HTML",
        )

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
            logger.error(f"Failed to notify applicant {user_id}: {e}")

        logger.info(f"Application {application_id} rejected by admin")


async def list_pending_applications(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """List all pending applications for admin."""
    if not is_admin_chat(update.message.chat.id):
        return

    pending = data_manager.pending_applications

    if not pending:
        await update.message.reply_text("📋 No pending applications.")
        return

    text = "📋 <b>Pending applications:</b>\n\n"

    for app_id, application in pending.items():
        applicant = application["applicant"]
        position = application["position"]
        text += f"• <b>{position}</b>: {applicant['name']} (@{applicant['telegram']})\n"
        text += f"  ID: <code>{app_id}</code>\n\n"

    await update.message.reply_text(text, parse_mode="HTML")
