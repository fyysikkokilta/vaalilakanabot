"""Register conversation handlers (user info for applications)."""

import re
from datetime import datetime
from typing import Union

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


async def _register_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE, is_finnish: bool
) -> Union[int, str]:
    """Shared start for registration; sets language and asks for name."""
    message = update.message
    if message is None or message.chat.type != "private":
        if message is not None:
            await message.reply_text(
                "Please use /register or /rekisteröidy in a private chat."
            )
        return ConversationHandler.END
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    chat_data["register_fi"] = is_finnish
    data_manager = context.bot_data.get("data_manager")
    if data_manager and update.effective_user is not None:
        existing = data_manager.sheets_manager.get_user_by_telegram_id(
            update.effective_user.id
        )
        if existing:
            intro = get_translation("register_update_intro", is_finnish)
            await message.reply_text(intro)
    text = get_translation("register_ask_name", is_finnish)
    await message.reply_text(text)
    return REGISTER_NAME


async def register_start_finnish(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Union[int, str]:
    """Start registration in Finnish (/rekisteröidy)."""
    return await _register_start(update, context, is_finnish=True)


async def register_start_english(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Union[int, str]:
    """Start registration in English (/register)."""
    return await _register_start(update, context, is_finnish=False)


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
    if "," in name:
        await message.reply_text(
            get_translation("name_no_commas", bool(chat_data.get("register_fi", True)))
        )
        return REGISTER_NAME
    if not name:
        await message.reply_text(
            get_translation("name_not_empty", bool(chat_data.get("register_fi", True)))
        )
        return REGISTER_NAME
    chat_data["register_name"] = name
    text = get_translation(
        "register_ask_email", bool(chat_data.get("register_fi", True))
    )
    await message.reply_text(text)
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
    if not is_valid_email(email):
        await message.reply_text(
            get_translation("email_invalid", bool(chat_data.get("register_fi", True)))
        )
        return REGISTER_EMAIL
    chat_data["register_email"] = email
    is_fi = bool(chat_data.get("register_fi", True))
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
    telegram_username = update.effective_user.username or ""
    user = UserRow(
        Telegram_ID=update.effective_user.id,
        Name=name,
        Email=email,
        Telegram=telegram_username,
        Show_On_Website_Consent=show_on_website,
        Updated_At=datetime.now().isoformat(),
    )
    data_manager.sheets_manager.upsert_user(user)
    chat_data.pop("register_name", None)
    chat_data.pop("register_email", None)
    is_finnish = bool(chat_data.get("register_fi", True))
    await query.edit_message_text(get_translation("register_done", is_finnish))
    return ConversationHandler.END


async def register_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Union[int, str]:
    """Cancel registration."""
    message = update.message
    chat_data = context.chat_data
    if chat_data is None:
        return ConversationHandler.END
    chat_data.pop("register_name", None)
    chat_data.pop("register_email", None)
    is_finnish = bool(chat_data.get("register_fi", True))
    if message is not None:
        await message.reply_text(get_translation("register_cancelled", is_finnish))
    return ConversationHandler.END
