"""User commands and basic functionality."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from .utils import vaalilakana_to_string

logger = logging.getLogger("vaalilakanabot")


async def register_channel(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Register a channel for announcements."""
    try:
        chat_id = update.message.chat.id
        data_manager.add_channel(chat_id)
        await update.message.reply_text(
            "Rekisteröity Vaalilakanabotin tiedotuskanavaksi!"
        )
    except Exception as e:
        logger.error(e)


async def show_vaalilakana(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Show the current vaalilakana."""
    try:
        vaalilakana_text = vaalilakana_to_string(
            data_manager.vaalilakana, data_manager.find_division_for_position
        )
        await update.message.reply_html(
            vaalilakana_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def jauhis(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Send jauhis sticker."""
    try:
        with open("assets/jauhis.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauhis %s", e)


async def jauh(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Send jauh sticker."""
    try:
        with open("assets/jauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauh %s", e)


async def jauho(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Send jauho sticker."""
    try:
        with open("assets/jauho.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauho %s", e)


async def lauh(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Send lauh sticker."""
    try:
        with open("assets/lauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Lauh %s", e)


async def mauh(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Send mauh sticker."""
    try:
        with open("assets/mauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Mauh %s", e)
