"""Register conversation handlers (user info for applications)."""

import re
from datetime import datetime

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
) -> int:
    """Shared start for registration; sets language and asks for name."""
    if update.message.chat.type != "private":
        msg = "Please use /register or /rekisteröidy in a private chat."
        await update.message.reply_text(msg)
        return ConversationHandler.END
    context.chat_data["register_fi"] = is_finnish
    data_manager = context.bot_data.get("data_manager")
    if data_manager:
        existing = data_manager.sheets_manager.get_user_by_telegram_id(
            update.effective_user.id
        )
        if existing:
            intro = get_translation("register_update_intro", is_finnish)
            await update.message.reply_text(intro)
    text = get_translation("register_ask_name", is_finnish)
    await update.message.reply_text(text)
    return REGISTER_NAME


async def register_start_finnish(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start registration in Finnish (/rekisteröidy)."""
    return await _register_start(update, context, is_finnish=True)


async def register_start_english(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start registration in English (/register)."""
    return await _register_start(update, context, is_finnish=False)


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store name and ask for email."""
    name = update.message.text.strip()
    if "," in name:
        await update.message.reply_text(
            get_translation(
                "name_no_commas", context.chat_data.get("register_fi", True)
            )
        )
        return REGISTER_NAME
    if not name:
        await update.message.reply_text(
            get_translation(
                "name_not_empty", context.chat_data.get("register_fi", True)
            )
        )
        return REGISTER_NAME
    context.chat_data["register_name"] = name
    text = get_translation(
        "register_ask_email", context.chat_data.get("register_fi", True)
    )
    await update.message.reply_text(text)
    return REGISTER_EMAIL


async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store email and ask for consent."""
    email = update.message.text.strip()
    if not is_valid_email(email):
        await update.message.reply_text(
            get_translation("email_invalid", context.chat_data.get("register_fi", True))
        )
        return REGISTER_EMAIL
    context.chat_data["register_email"] = email
    text = get_translation(
        "register_consent", context.chat_data.get("register_fi", True)
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_translation("yes", context.chat_data.get("register_fi", True)),
                    callback_data="register_consent_yes",
                ),
                InlineKeyboardButton(
                    get_translation("no", context.chat_data.get("register_fi", True)),
                    callback_data="register_consent_no",
                ),
            ]
        ]
    )
    await update.message.reply_text(text, reply_markup=keyboard)
    return REGISTER_CONSENT


async def register_consent(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> int:
    """Store consent and save user."""
    query = update.callback_query
    await query.answer()
    if query.data != "register_consent_yes" and query.data != "register_consent_no":
        return REGISTER_CONSENT
    show_on_website = query.data == "register_consent_yes"
    name = context.chat_data.get("register_name", "")
    email = context.chat_data.get("register_email", "")
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
    context.chat_data.pop("register_name", None)
    context.chat_data.pop("register_email", None)
    is_finnish = context.chat_data.get("register_fi", True)
    await query.edit_message_text(get_translation("register_done", is_finnish))
    return ConversationHandler.END


async def register_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel registration."""
    context.chat_data.pop("register_name", None)
    context.chat_data.pop("register_email", None)
    is_finnish = context.chat_data.get("register_fi", True)
    await update.message.reply_text(get_translation("register_cancelled", is_finnish))
    return ConversationHandler.END
