"""Admin approval handlers for elected role applications."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .config import ADMIN_CHAT_ID
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

    text = (
        f"🗳️ <b>Uusi hakemus vaaleilla valittavaan virkaan</b>\n\n"
        f"<b>Virka:</b> {position}\n"
        f"<b>Jaos:</b> {division}\n"
        f"<b>Nimi:</b> {applicant['name']}\n"
        f"<b>Sähköposti:</b> {applicant['email']}\n"
        f"<b>Telegram:</b> @{applicant['telegram']}\n\n"
        f"Hyväksytäänkö hakemus?"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Hyväksy", callback_data=f"approve_{application_id}"
            ),
            InlineKeyboardButton("❌ Hylkää", callback_data=f"reject_{application_id}"),
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
    if str(query.message.chat.id) != str(ADMIN_CHAT_ID):
        await query.answer("Tämä toiminto on vain admineille.", show_alert=True)
        return

    callback_data = query.data
    if not (
        callback_data.startswith("approve_") or callback_data.startswith("reject_")
    ):
        return

    action, application_id = callback_data.split("_", 1)
    application = data_manager.get_pending_application(application_id)

    if not application:
        await query.edit_message_text(
            "❌ Hakemusta ei löytynyt tai se on jo käsitelty."
        )
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
                f"✅ <b>Hakemus hyväksytty!</b>\n\n"
                f"<b>Virka:</b> {position}\n"
                f"<b>Hakija:</b> {applicant['name']}\n\n"
                f"Hakemus on lisätty vaalilakanaan ja ilmoitus lähetetty kanaviin.",
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
            await query.edit_message_text("❌ Virhe hakemuksen hyväksynnässä.")

    elif action == "reject":
        # Reject the application
        data_manager.remove_pending_application(application_id)
        await query.edit_message_text(
            f"❌ <b>Hakemus hylätty!</b>\n\n"
            f"<b>Virka:</b> {position}\n"
            f"<b>Hakija:</b> {applicant['name']}\n\n"
            f"Hakemus on hylätty eikä sitä lisätä vaalilakanaan.",
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
    chat_id = update.message.chat.id
    if str(chat_id) != str(ADMIN_CHAT_ID):
        return

    pending = data_manager.pending_applications

    if not pending:
        await update.message.reply_text("📋 Ei odottavia hakemuksia.")
        return

    text = "📋 <b>Odottavat hakemukset:</b>\n\n"

    for app_id, application in pending.items():
        applicant = application["applicant"]
        position = application["position"]
        text += f"• <b>{position}</b>: {applicant['name']} (@{applicant['telegram']})\n"
        text += f"  ID: <code>{app_id}</code>\n\n"

    await update.message.reply_text(text, parse_mode="HTML")
