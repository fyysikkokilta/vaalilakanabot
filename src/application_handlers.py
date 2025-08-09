"""Application conversation handlers."""

import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes

from .config import (
    SELECTING_DIVISION,
    SELECTING_ROLE,
    GIVING_NAME,
    GIVING_EMAIL,
    CONFIRMING_APPLICATION,
)
from .utils import generate_keyboard
from .admin_approval import send_admin_approval_request
from .sheets_data_manager import DataManager

logger = logging.getLogger("vaalilakanabot")


def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    # Simple regex pattern for basic email validation
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


async def hae(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Apply for a position in Finnish."""
    chat_data = context.chat_data
    chat_data["is_finnish"] = True

    localized_divisions, callback_data = data_manager.get_divisions(True)
    keyboard = generate_keyboard(localized_divisions, callback_data)

    await update.message.reply_text(
        "Minkä jaoksen virkaan haet?",
        reply_markup=keyboard,
    )
    return SELECTING_DIVISION


async def apply(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Apply for a position in English."""
    chat_data = context.chat_data
    chat_data["is_finnish"] = False

    localized_divisions, callback_data = data_manager.get_divisions(False)
    keyboard = generate_keyboard(localized_divisions, callback_data)

    await update.message.reply_text(
        "For which division are you applying?",
        reply_markup=keyboard,
    )
    return SELECTING_DIVISION


async def select_division(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Handle division selection."""
    query = update.callback_query
    chat_data = context.chat_data
    await query.answer()
    chat_data["division"] = query.data

    localized_positions, callback_data = data_manager.get_positions(
        query.data, chat_data["is_finnish"]
    )
    keyboard = generate_keyboard(
        localized_positions,
        callback_data,
        back=("Takaisin" if chat_data["is_finnish"] else "Back"),
    )

    text = (
        "Mihin rooliin haet?"
        if chat_data["is_finnish"]
        else "What position are you applying to?"
    )
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
    )
    return SELECTING_ROLE


async def select_role(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Handle role selection."""
    query = update.callback_query
    chat_data = context.chat_data
    await query.answer()

    user_id = update.effective_user.id
    position = query.data

    # Check if user already has an approved application
    if data_manager.check_applicant_exists(position, user_id):
        text = (
            "Olet jo hakenut tähän rooliin!"
            if chat_data["is_finnish"]
            else "You have already applied to this position!"
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    # Check if user has a pending application for elected roles
    role_row = data_manager.find_role_by_name(position)
    is_elected_type = role_row and role_row.get("Type") in ("BOARD", "ELECTED")
    if is_elected_type and data_manager.check_pending_application_exists(
        position, user_id
    ):
        text = (
            "Sinulla on jo odottava hakemus tähän rooliin!"
            if chat_data["is_finnish"]
            else "You already have a pending application for this position!"
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    # Check if user already has an approved or pending application for any elected role
    if is_elected_type:
        has_elected_application = False
        elected_position = ""

        # Check for approved applications to elected roles
        for role_title, role_data in data_manager.vaalilakana.items():
            if role_data.get("type") in ("BOARD", "ELECTED"):
                for applicant in role_data.get("applicants", []):
                    if applicant["user_id"] == user_id:
                        has_elected_application = True
                        elected_position = role_title
                        break
            if has_elected_application:
                break

        # Check for pending applications to elected roles using Applications sheet rows
        if not has_elected_application:
            for app_row in data_manager.pending_applications:
                if int(app_row.get("Telegram_ID", 0)) != int(user_id):
                    continue

                role_id = app_row.get("Role_ID", "")
                if not role_id:
                    continue
                # Find role by ID and ensure it's an elected type
                roles = data_manager.get_all_roles()
                rr = next((r for r in roles if r.get("ID") == role_id), None)
                if rr and rr.get("Type") in ("BOARD", "ELECTED"):
                    has_elected_application = True
                    elected_position = rr.get("Role_FI", "") or rr.get("Role_EN", "")
                    break

        if has_elected_application:
            warning_text = (
                (
                    f"⚠️ <b>Varoitus: Olet jo hakenut vaaleilla valittavaan virkaan!</b>\n\n"
                    f"Olet jo hakenut virkaan: <b>{elected_position}</b>\n\n"
                    f"Jos sinulla on vararooleja, kerro niistä raadille suoraan.\n\n"
                    f"Haluatko jatkaa hakemusta tähän rooliin?"
                )
                if chat_data["is_finnish"]
                else (
                    f"⚠️ <b>Warning: You have already applied to an elected position!</b>\n\n"
                    f"You have already applied to: <b>{elected_position}</b>\n\n"
                    f"If you have backup roles, tell the board directly.\n\n"
                    f"Do you want to continue with this application?"
                )
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Jatka" if chat_data["is_finnish"] else "Continue",
                            callback_data="continue_multiple",
                        ),
                        InlineKeyboardButton(
                            "Peruuta" if chat_data["is_finnish"] else "Cancel",
                            callback_data="cancel_multiple",
                        ),
                    ]
                ]
            )

            await query.edit_message_text(
                warning_text, reply_markup=keyboard, parse_mode="HTML"
            )
            chat_data["position"] = position
            chat_data["loc_position"] = (
                chat_data["position"]
                if chat_data["is_finnish"]
                else (
                    data_manager.find_role_by_name(position, chat_data["division"])
                    or {}
                ).get("Role_EN", position)
            )
            chat_data["is_elected"] = True
            return SELECTING_ROLE

    chat_data["position"] = position
    chat_data["loc_position"] = (
        chat_data["position"]
        if chat_data["is_finnish"]
        else (
            data_manager.find_role_by_name(position, chat_data["division"]) or {}
        ).get("Role_EN", position)
    )
    chat_data["is_elected"] = bool(is_elected_type)

    elected_role_text = "vaaleilla valittavaan " if chat_data["is_elected"] else ""
    elected_role_text_en = "elected " if chat_data["is_elected"] else ""

    text = (
        f"Haet {elected_role_text}rooliin: {chat_data['loc_position']}. Mikä on nimesi?"
        if chat_data["is_finnish"]
        else f"You are applying to the {elected_role_text_en}role: {chat_data['loc_position']}. What is your name?"
    )
    await query.edit_message_text(
        text=text,
    )
    return GIVING_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle name input."""
    chat_data = context.chat_data
    name = update.message.text.strip()

    # Validate that name doesn't contain commas (interferes with admin commands)
    if "," in name:
        error_text = (
            "Nimi ei voi sisältää pilkkuja. Anna nimesi uudelleen:"
            if chat_data["is_finnish"]
            else "Name cannot contain commas. Please enter your name again:"
        )
        await update.message.reply_text(error_text)
        return GIVING_NAME

    # Validate that name is not empty after stripping
    if not name:
        error_text = (
            "Nimi ei voi olla tyhjä. Anna nimesi:"
            if chat_data["is_finnish"]
            else "Name cannot be empty. Please enter your name:"
        )
        await update.message.reply_text(error_text)
        return GIVING_NAME

    chat_data["name"] = name
    text = (
        "Mikä on sähköpostiosoitteesi?"
        if chat_data["is_finnish"]
        else "What is your email address?"
    )
    await update.message.reply_text(text)
    return GIVING_EMAIL


async def enter_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle email input."""
    chat_data = context.chat_data
    email = update.message.text.strip()

    # Validate email format
    if not is_valid_email(email):
        error_text = (
            "Sähköpostiosoite ei ole kelvollinen. Anna sähköpostiosoite muodossa: nimi@domain.fi"
            if chat_data["is_finnish"]
            else "Email address is not valid. Please provide an email in format: name@domain.com"
        )
        await update.message.reply_text(error_text)
        return GIVING_EMAIL  # Stay in the same state to ask for email again

    chat_data["email"] = email
    chat_data["telegram"] = update.message.from_user.username

    elected_text = (
        " (Hakemus vaatii admin-hyväksynnän ennen lisäämistä vaalilakanaan)"
        if chat_data["is_elected"]
        else ""
    )
    elected_text_en = (
        " (Application requires admin approval before being added to the election sheet)"
        if chat_data["is_elected"]
        else ""
    )

    text = (
        (
            f"Hakemuksesi tiedot: \n"
            f"<b>Haettava rooli</b>: {chat_data['loc_position']}\n"
            f"<b>Nimi</b>: {chat_data['name']}\n"
            f"<b>Sähköposti</b>: {chat_data['email']}\n"
            f"<b>Telegram</b>: {chat_data['telegram']}\n\n"
            f"Haluatko lähettää hakemuksen{elected_text}?"
        )
        if chat_data["is_finnish"]
        else (
            f"Your application details: \n"
            f"<b>Position</b>: {chat_data['loc_position']}\n"
            f"<b>Name</b>: {chat_data['name']}\n"
            f"<b>Email</b>: {chat_data['email']}\n"
            f"<b>Telegram</b>: {chat_data['telegram']}\n\n"
            f"Do you want to send the application {elected_text_en}?"
        )
    )
    text_yes = "Kyllä" if chat_data["is_finnish"] else "Yes"
    text_no = "En" if chat_data["is_finnish"] else "No"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text_yes, callback_data="yes"),
                InlineKeyboardButton(text_no, callback_data="no"),
            ]
        ]
    )

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
    return CONFIRMING_APPLICATION


async def confirm_application(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Handle application confirmation."""
    query = update.callback_query
    chat_data = context.chat_data

    await query.answer()
    try:
        if query.data == "yes":
            name = chat_data["name"]
            position = chat_data["position"]
            email = chat_data["email"]
            telegram = chat_data["telegram"]

            new_applicant = {
                "user_id": update.effective_user.id,
                "name": name,
                "email": email,
                "telegram": telegram,
                "fiirumi": "",
                "status": "",
            }

            # Check if this is an elected role that needs admin approval via Role Type
            role_row = data_manager.find_role_by_name(position)
            needs_approval = role_row and role_row.get("Type") in ("BOARD", "ELECTED")
            if needs_approval:
                # Create pending application
                application_data = {
                    "applicant": new_applicant,
                    "position": position,
                    "language": "fi" if chat_data["is_finnish"] else "en",
                }

                # Add to pending applications
                data_manager.add_pending_application(application_data)

                # Send admin approval request
                await send_admin_approval_request(
                    context,
                    data_manager,
                    f"{role_row['ID']}_{new_applicant['user_id']}",
                    application_data,
                )

                text = (
                    "Hakemuksesi on lähetetty ja odottaa admin-hyväksyntää. Saat ilmoituksen kun hakemus on käsitelty."
                    if chat_data["is_finnish"]
                    else "Your application has been sent and is awaiting admin approval. You will be notified when it's processed."
                )
            else:
                # For non-elected roles, add directly with APPROVED status
                new_applicant["status"] = "APPROVED"
                language = "fi" if chat_data["is_finnish"] else "en"
                data_manager.add_applicant(position, new_applicant, language)

                text = (
                    "Hakemuksesi on vastaanotettu. Kiitos!"
                    if chat_data["is_finnish"]
                    else "Your application has been received. Thank you!"
                )

            await query.edit_message_text(text, reply_markup=None)
        else:
            text = (
                "Hakemuksesi on peruttu."
                if chat_data["is_finnish"]
                else "Your application has been cancelled."
            )
            await query.edit_message_text(text, reply_markup=None)

    except Exception as e:
        logger.error(e)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current operation."""
    chat_data = context.chat_data
    chat_data.clear()
    await update.message.reply_text("Cancelled current operation.")
    return ConversationHandler.END


async def handle_back_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Handle back button press to return to division selection."""
    query = update.callback_query
    chat_data = context.chat_data
    await query.answer()

    # Go back to division selection
    localized_divisions, callback_data = data_manager.get_divisions(
        chat_data["is_finnish"]
    )
    keyboard = generate_keyboard(localized_divisions, callback_data)

    text = (
        "Minkä jaoksen virkaan haet?"
        if chat_data["is_finnish"]
        else "For which division are you applying?"
    )
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
    )
    return SELECTING_DIVISION


async def handle_multiple_application_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle user choice when applying to multiple elected roles."""
    query = update.callback_query
    chat_data = context.chat_data
    await query.answer()

    if query.data == "cancel_multiple":
        text = (
            "Hakemus peruttu." if chat_data["is_finnish"] else "Application cancelled."
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    elif query.data == "continue_multiple":
        # Continue with the application
        elected_role_text = "vaaleilla valittavaan " if chat_data["is_elected"] else ""
        elected_role_text_en = "elected " if chat_data["is_elected"] else ""

        text = (
            f"Haet {elected_role_text}rooliin: {chat_data['loc_position']}. Mikä on nimesi?"
            if chat_data["is_finnish"]
            else f"You are applying to the {elected_role_text_en}role: {chat_data['loc_position']}. What is your name?"
        )
        await query.edit_message_text(text=text)
        return GIVING_NAME

    return ConversationHandler.END
