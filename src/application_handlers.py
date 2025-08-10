"""Application conversation handlers."""

import logging
import re
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes

from src.types import ApplicationRow

from .config import (
    SELECTING_DIVISION,
    SELECTING_ROLE,
    GIVING_NAME,
    GIVING_EMAIL,
    CONFIRMING_APPLICATION,
)
from .utils import generate_keyboard, get_translation, get_role_name
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
        get_translation("select_division", chat_data.get("is_finnish", False)),
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
        get_translation("select_division", chat_data.get("is_finnish", False)),
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
        query.data, chat_data.get("is_finnish", False)
    )
    keyboard = generate_keyboard(
        localized_positions,
        callback_data,
        back=get_translation("back", chat_data.get("is_finnish", False)),
    )

    text = get_translation("select_role", chat_data.get("is_finnish", False))
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
    role_id = query.data

    # Check if user already has any application (approved or pending) for this position
    role_row = data_manager.get_role_by_id(role_id)
    is_elected_type = role_row and role_row.get("Type") in ("BOARD", "ELECTED")

    if not role_row:
        await query.edit_message_text("Role not found.")
        return ConversationHandler.END

    user_applications = data_manager.get_applications_for_user(user_id)
    existing_application = next(
        (app for app in user_applications if app.get("Role_ID") == role_id),
        None,
    )

    if existing_application:
        if existing_application.get("Status", "PENDING") == "APPROVED":
            key = "already_applied"
        elif existing_application.get("Status", "PENDING") == "ELECTED":
            key = "already_elected"
        else:  # Status is pending
            key = "pending_application"

        text = get_translation(key, chat_data.get("is_finnish", False))
        await query.edit_message_text(text)
        return ConversationHandler.END

    # Check if user already has an approved or pending application for any elected role
    if is_elected_type:
        other_roles = []

        # Check for any applications (approved or pending) to elected roles
        for application in user_applications:
            app_role = data_manager.get_role_by_id(application.get("Role_ID", ""))

            if app_role and app_role.get("Type") in ("BOARD", "ELECTED"):
                other_roles.append(app_role)

        if other_roles:
            warning_text = get_translation(
                "multiple_application_warning",
                chat_data.get("is_finnish", False),
                elected_positions=", ".join(
                    [
                        get_role_name(role, chat_data.get("is_finnish", False))
                        for role in other_roles
                    ]
                ),
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            get_translation(
                                "continue", chat_data.get("is_finnish", False)
                            ),
                            callback_data="continue_multiple",
                        ),
                        InlineKeyboardButton(
                            get_translation(
                                "cancel", chat_data.get("is_finnish", False)
                            ),
                            callback_data="cancel_multiple",
                        ),
                    ]
                ]
            )

            await query.edit_message_text(
                warning_text, reply_markup=keyboard, parse_mode="HTML"
            )
            chat_data["role_id"] = role_id
            chat_data["is_elected"] = True
            return SELECTING_ROLE

    chat_data["role_id"] = role_id
    chat_data["is_elected"] = bool(is_elected_type)

    elected_text = (
        get_translation("elected_role_prefix", chat_data.get("is_finnish", False))
        if chat_data.get("is_elected", False)
        else ""
    )

    text = get_translation(
        "ask_name",
        chat_data.get("is_finnish", False),
        elected_text=elected_text,
        position=get_role_name(role_row, chat_data.get("is_finnish", False)),
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
        error_text = get_translation(
            "name_no_commas", chat_data.get("is_finnish", False)
        )
        await update.message.reply_text(error_text)
        return GIVING_NAME

    # Validate that name is not empty after stripping
    if not name:
        error_text = get_translation(
            "name_not_empty", chat_data.get("is_finnish", False)
        )
        await update.message.reply_text(error_text)
        return GIVING_NAME

    chat_data["name"] = name
    text = get_translation("ask_email", chat_data.get("is_finnish", False))
    await update.message.reply_text(text)
    return GIVING_EMAIL


async def enter_email(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Handle email input."""
    chat_data = context.chat_data
    email = update.message.text.strip()

    # Validate email format
    if not is_valid_email(email):
        error_text = get_translation(
            "email_invalid", chat_data.get("is_finnish", False)
        )
        await update.message.reply_text(error_text)
        return GIVING_EMAIL  # Stay in the same state to ask for email again

    chat_data["email"] = email
    chat_data["telegram"] = update.message.from_user.username

    elected_text = (
        get_translation("admin_approval_note", chat_data.get("is_finnish", False))
        if chat_data.get("is_elected", False)
        else ""
    )

    role_row = data_manager.get_role_by_id(chat_data.get("role_id", ""))

    text = get_translation(
        "application_details",
        chat_data.get("is_finnish", False),
        position=get_role_name(role_row, chat_data.get("is_finnish", False)),
        name=chat_data.get("name", ""),
        email=chat_data.get("email", ""),
        telegram=chat_data.get("telegram", ""),
        elected_text=elected_text,
    )

    text_yes = get_translation("yes", chat_data.get("is_finnish", False))
    text_no = get_translation("no", chat_data.get("is_finnish", False))
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
            role_row = data_manager.get_role_by_id(chat_data.get("role_id", ""))

            new_applicant = ApplicationRow(
                Timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                Role_ID=role_row.get("ID", ""),
                Telegram_ID=update.effective_user.id,
                Name=chat_data.get("name", ""),
                Email=chat_data.get("email", ""),
                Telegram=chat_data.get("telegram", ""),
                Fiirumi_Post="",
                Status="PENDING",
                Language="fi" if chat_data.get("is_finnish", False) else "en",
            )

            # Check if this is an elected role that needs admin approval via Role Type
            needs_approval = role_row and role_row.get("Type") in ("BOARD", "ELECTED")
            if needs_approval:

                # Add to pending applications
                data_manager.add_applicant(new_applicant)

                # Send admin approval request
                await send_admin_approval_request(
                    context,
                    data_manager,
                    new_applicant,
                )

                text = get_translation(
                    "application_awaiting_approval", chat_data.get("is_finnish", False)
                )
            else:
                # For non-elected roles, add directly with APPROVED status
                new_applicant["Status"] = "APPROVED"
                data_manager.add_applicant(new_applicant)

                text = get_translation(
                    "application_received", chat_data.get("is_finnish", False)
                )

            await query.edit_message_text(text, reply_markup=None)
        else:
            text = get_translation(
                "application_cancelled_full", chat_data.get("is_finnish", False)
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
        chat_data.get("is_finnish", False)
    )
    keyboard = generate_keyboard(localized_divisions, callback_data)

    text = get_translation("select_division", chat_data.get("is_finnish", False))
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
        text = get_translation(
            "application_cancelled", chat_data.get("is_finnish", False)
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    elif query.data == "continue_multiple":
        # Continue with the application
        elected_text = (
            get_translation("elected_role_prefix", chat_data.get("is_finnish", False))
            if chat_data.get("is_elected", False)
            else ""
        )

        text = get_translation(
            "ask_name",
            chat_data.get("is_finnish", False),
            elected_text=elected_text,
            position=chat_data.get("loc_position", ""),
        )
        await query.edit_message_text(text=text)
        return GIVING_NAME

    return ConversationHandler.END
