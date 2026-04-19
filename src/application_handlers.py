"""Application conversation handlers."""

import logging
from datetime import datetime
from typing import Any, Dict, Tuple, Union

from telegram import CallbackQuery, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes

from .types import ApplicationRow, ElectionStructureRow
from .config import (
    SELECTING_DIVISION,
    SELECTING_ROLE,
    CONFIRMING_APPLICATION,
)
from .utils import (
    generate_keyboard,
    get_translation,
    get_role_name,
    is_active_application,
)
from .admin_approval import send_admin_approval_request
from .sheets_data_manager import DataManager

logger = logging.getLogger("vaalilakanabot")


async def _load_user_into_chat_data(
    user_id: int,
    chat_data: Dict[str, Any],
    query: CallbackQuery,
    update: Update,
    data_manager: DataManager,
) -> bool:
    """Fetch the registered user and populate chat_data with name/email/telegram.

    Returns False (and sends an error reply) if the user is not registered.
    """
    is_finnish = bool(chat_data.get("is_finnish", False))
    user = data_manager.get_user_by_telegram_id(user_id)
    if not user:
        await query.edit_message_text(
            get_translation("please_register_first", is_finnish)
        )
        return False
    chat_data["name"] = user.get("Name", "")
    chat_data["email"] = user.get("Email", "")
    chat_data["telegram"] = user.get("Telegram", "") or (
        update.effective_user.username if update.effective_user else ""
    )
    return True


async def _start_application(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data_manager: DataManager,
    is_finnish: bool,
) -> Union[int, str]:
    """Common entry point for the application conversation."""
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END
    if context.chat_data is None:
        return ConversationHandler.END
    chat_data: Dict[str, Any] = context.chat_data
    user_id = update.effective_user.id
    if not data_manager.get_user_by_telegram_id(user_id):
        await update.message.reply_text(
            get_translation("please_register_first", is_finnish)
        )
        return ConversationHandler.END

    chat_data["is_finnish"] = is_finnish

    localized_divisions, callback_data = data_manager.get_divisions(is_finnish)
    keyboard = generate_keyboard(localized_divisions, callback_data)

    await update.message.reply_text(
        get_translation("select_division", is_finnish),
        reply_markup=keyboard,
    )
    return SELECTING_DIVISION


async def hae(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Apply for a position in Finnish."""
    return await _start_application(update, context, data_manager, True)


async def apply(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Apply for a position in English."""
    return await _start_application(update, context, data_manager, False)


async def select_division(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Handle division selection."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    await query.answer()
    query_data: str = query.data or ""
    chat_data["division"] = query_data
    is_fi = bool(chat_data.get("is_finnish", False))

    localized_positions, callback_data = data_manager.get_positions(query_data, is_fi)
    keyboard = generate_keyboard(
        localized_positions,
        callback_data,
        back=get_translation("back", is_fi),
    )

    text = get_translation("select_role", is_fi)
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
    )
    return SELECTING_ROLE


def _existing_application_message_key(application: ApplicationRow) -> str:
    """Return translation key for already-applied state."""
    status = application.get("Status", "")
    if status == "APPROVED":
        return "already_applied"
    if status == "ELECTED":
        return "already_elected"
    return "pending_application"


def _build_confirm_application_ui(
    chat_data: Dict[str, Any], role_row: ElectionStructureRow
) -> Tuple[str, InlineKeyboardMarkup]:
    """Return (message_text, reply_markup) for application confirmation step."""
    is_fi = chat_data.get("is_finnish", False)
    elected_text = (
        get_translation("admin_approval_note", is_fi)
        if chat_data.get("is_elected", False)
        else ""
    )
    text = get_translation(
        "application_details",
        is_fi,
        position=get_role_name(role_row, is_fi),
        name=chat_data.get("name", ""),
        email=chat_data.get("email", ""),
        telegram=chat_data.get("telegram", ""),
        elected_text=elected_text,
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_translation("yes", is_fi), callback_data="yes"
                ),
                InlineKeyboardButton(get_translation("no", is_fi), callback_data="no"),
            ]
        ]
    )
    return text, keyboard


async def _send_multiple_elected_warning(
    query: CallbackQuery,
    chat_data: Dict[str, Any],
    other_roles: list[ElectionStructureRow],
    role_id: str,
) -> bool:
    """Send warning keyboard and set chat_data; return True."""
    is_fi = bool(chat_data.get("is_finnish", False))
    warning_text = get_translation(
        "multiple_application_warning",
        is_fi,
        elected_positions=", ".join(get_role_name(role, is_fi) for role in other_roles),
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_translation("continue", is_fi),
                    callback_data="continue_multiple",
                ),
                InlineKeyboardButton(
                    get_translation("cancel", is_fi),
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
    return True


async def select_role(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Handle role selection."""
    query = update.callback_query
    if query is None or update.effective_user is None:
        return ConversationHandler.END
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    await query.answer()
    user_id = update.effective_user.id
    role_id = query.data or ""
    role_row = data_manager.get_role_by_id(role_id)
    if not role_row:
        await query.edit_message_text("Role not found.")
        return ConversationHandler.END

    is_elected_type = role_row.get("Type") in ("BOARD", "ELECTED")

    user_applications = data_manager.get_applications_for_user(user_id)
    existing_application = next(
        (
            app
            for app in user_applications
            if app.get("Role_ID") == role_id and is_active_application(app)
        ),
        None,
    )

    is_fi = bool(chat_data.get("is_finnish", False))

    if existing_application:
        text = get_translation(
            _existing_application_message_key(existing_application),
            is_fi,
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    if is_elected_type:
        other_roles = data_manager.get_other_elected_roles_for_user(user_id, role_id)
        if other_roles:
            await _send_multiple_elected_warning(query, chat_data, other_roles, role_id)
            return SELECTING_ROLE

    chat_data["role_id"] = role_id
    chat_data["is_elected"] = bool(is_elected_type)

    if not await _load_user_into_chat_data(
        user_id, chat_data, query, update, data_manager
    ):
        return ConversationHandler.END

    text, keyboard = _build_confirm_application_ui(chat_data, role_row)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    return CONFIRMING_APPLICATION


async def confirm_application(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Handle application confirmation."""
    query = update.callback_query
    if query is None or update.effective_user is None:
        return ConversationHandler.END
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    is_fi = bool(chat_data.get("is_finnish", False))

    await query.answer()
    try:
        if query.data == "yes":
            role_id_str = str(chat_data.get("role_id", ""))
            role_row = data_manager.get_role_by_id(role_id_str)

            new_applicant: ApplicationRow = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Role_ID": role_row.get("ID", "") if role_row else role_id_str,
                "Telegram_ID": update.effective_user.id,
                "Fiirumi_Post": "",
                "Status": "PENDING",
                "Language": "fi" if is_fi else "en",
                "Group_ID": None,
            }

            # Check if this is an elected role that needs admin approval via Role Type
            needs_approval = role_row is not None and role_row.get("Type") in (
                "BOARD",
                "ELECTED",
                "AUDITOR",
            )
            if needs_approval:

                # Add to pending applications
                data_manager.add_applicant(new_applicant)

                # Send admin approval request
                await send_admin_approval_request(
                    context,
                    data_manager,
                    new_applicant,
                )

                text = get_translation("application_awaiting_approval", is_fi)
            else:
                # For non-elected roles, add directly with APPROVED status
                new_applicant["Status"] = "APPROVED"
                data_manager.add_applicant(new_applicant)

                text = get_translation("application_received", is_fi)

            await query.edit_message_text(text, reply_markup=None)
        else:
            text = get_translation("application_cancelled_full", is_fi)
            await query.edit_message_text(text, reply_markup=None)

    except Exception as e:
        logger.error(e)
        try:
            await query.edit_message_text("An error occurred. Please try again.")
        except Exception:
            pass

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current operation."""
    chat_data = context.chat_data
    if chat_data is not None:
        chat_data.clear()
    message = update.message
    if message is not None:
        await message.reply_text("Cancelled current operation.")
    return ConversationHandler.END


async def handle_back_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Handle back button press to return to division selection."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    await query.answer()
    is_fi = bool(chat_data.get("is_finnish", False))

    # Go back to division selection
    localized_divisions, callback_data = data_manager.get_divisions(is_fi)
    keyboard = generate_keyboard(localized_divisions, callback_data)

    text = get_translation("select_division", is_fi)
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
    )
    return SELECTING_DIVISION


async def handle_multiple_application_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Handle user choice when applying to multiple elected roles."""
    query = update.callback_query
    if query is None or update.effective_user is None:
        return ConversationHandler.END
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    await query.answer()

    if query.data == "cancel_multiple":
        text = get_translation(
            "application_cancelled", bool(chat_data.get("is_finnish", False))
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    if query.data == "continue_multiple":
        user_id = update.effective_user.id
        if not await _load_user_into_chat_data(
            user_id, chat_data, query, update, data_manager
        ):
            return ConversationHandler.END
        role_row = data_manager.get_role_by_id(str(chat_data.get("role_id", "")))
        if not role_row:
            await query.edit_message_text("Role not found.")
            return ConversationHandler.END
        text, keyboard = _build_confirm_application_ui(chat_data, role_row)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        return CONFIRMING_APPLICATION

    return ConversationHandler.END
