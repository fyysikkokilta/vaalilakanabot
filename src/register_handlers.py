"""Register conversation handlers (user info for applications)."""

import re
from datetime import datetime
from typing import Any, Mapping, Union

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes

from .types import UserRow
from .config import REGISTER_NAME, REGISTER_EMAIL, REGISTER_CONSENT
from .utils import get_translation
from .sheets_data_manager import DataManager


def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def _is_fi(chat_data: Mapping[str, Any]) -> bool:
    """Return True when the registration flow is in Finnish (default)."""
    return bool(chat_data.get("register_fi", True))


async def _register_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data_manager: DataManager,
    is_finnish: bool,
) -> Union[int, str]:
    """Shared start for registration; sets language and asks for name."""
    message = update.message
    if message is None or message.chat.type != "private":
        if message is not None:
            await message.reply_text(
                "Please use /register or /rekisteroidy in a private chat."
            )
        return ConversationHandler.END
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    chat_data["register_fi"] = is_finnish
    if update.effective_user is not None:
        existing = data_manager.get_user_by_telegram_id(update.effective_user.id)
        if existing:
            intro = get_translation("register_update_intro", is_finnish)
            await message.reply_text(intro)
    text = get_translation("register_ask_name", is_finnish)
    await message.reply_text(text)
    return REGISTER_NAME


async def register_start_finnish(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Start registration in Finnish (/rekisteroidy)."""
    return await _register_start(update, context, data_manager, is_finnish=True)


async def register_start_english(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Start registration in English (/register)."""
    return await _register_start(update, context, data_manager, is_finnish=False)


async def register_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Union[int, str]:
    """Store name and ask for email."""
    message = update.message
    chat_data = context.chat_data
    if message is None or chat_data is None:
        return ConversationHandler.END
    text_content = message.text
    name = (text_content or "").strip()
    is_fi = _is_fi(chat_data)
    if "," in name:
        await message.reply_text(get_translation("name_no_commas", is_fi))
        return REGISTER_NAME
    if not name:
        await message.reply_text(get_translation("name_not_empty", is_fi))
        return REGISTER_NAME
    chat_data["register_name"] = name
    await message.reply_text(get_translation("register_ask_email", is_fi))
    return REGISTER_EMAIL


async def register_email(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Union[int, str]:
    """Store email and ask for consent."""
    message = update.message
    chat_data = context.chat_data
    if message is None or chat_data is None:
        return ConversationHandler.END
    text_content = message.text
    email = (text_content or "").strip()
    is_fi = _is_fi(chat_data)
    if not is_valid_email(email):
        await message.reply_text(get_translation("email_invalid", is_fi))
        return REGISTER_EMAIL
    chat_data["register_email"] = email
    text = get_translation("register_consent", is_fi)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_translation("yes", is_fi),
                    callback_data="register_consent_yes",
                ),
                InlineKeyboardButton(
                    get_translation("no", is_fi),
                    callback_data="register_consent_no",
                ),
            ]
        ]
    )
    await message.reply_text(text, reply_markup=keyboard)
    return REGISTER_CONSENT


async def register_consent(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Union[int, str]:
    """Store consent and save user."""
    query = update.callback_query
    chat_data = context.chat_data
    if query is None or update.effective_user is None or chat_data is None:
        return ConversationHandler.END
    await query.answer()
    query_data = query.data
    if query_data not in ("register_consent_yes", "register_consent_no"):
        return REGISTER_CONSENT
    show_on_website = query_data == "register_consent_yes"
    name = str(chat_data.get("register_name", ""))
    email = str(chat_data.get("register_email", ""))
    telegram_username = (
        f"@{update.effective_user.username}" if update.effective_user.username else ""
    )
    user = UserRow(
        Telegram_ID=update.effective_user.id,
        Name=name,
        Email=email,
        Telegram=telegram_username,
        Show_On_Website_Consent=show_on_website,
        Updated_At=datetime.now().isoformat(),
    )
    data_manager.upsert_user(user)
    chat_data.pop("register_name", None)
    chat_data.pop("register_email", None)
    await query.edit_message_text(get_translation("register_done", _is_fi(chat_data)))
    return ConversationHandler.END


async def register_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Union[int, str]:
    """Cancel registration."""
    message = update.message
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    is_fi = _is_fi(chat_data)
    chat_data.pop("register_name", None)
    chat_data.pop("register_email", None)
    chat_data.pop("register_fi", None)
    if message is not None:
        await message.reply_text(get_translation("register_cancelled", is_fi))
    return ConversationHandler.END
