"""User commands and basic functionality."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from .utils import vaalilakana_to_string, vaalilakana_to_string_en

logger = logging.getLogger("vaalilakanabot")


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Show help information for users in English."""
    try:
        help_text = """
🤖 <b>Vaalilakanabot - User Commands</b>

<b>Basic Commands:</b>
• /start - Register channel for announcements
• /lakana - Show current vaalilakana (Finnish)
• /sheet - Show current election sheet (English)
• /hae - Apply for a position in Finnish (send in private chat)
• /apply - Apply for a position in English (send in private chat)

<b>Fun Commands:</b>
• /jauhis - Send jauhis sticker
• /jauh - Send jauh sticker  
• /jauho - Send jauho sticker
• /lauh - Send lauh sticker
• /mauh - Send mauh sticker

<b>Additional Information:</b>
• Use /hae in private message to apply in Finnish
• Use /apply in private message to apply in English
• Vaalilakana updates automatically
• Applications for elected positions require admin approval

<b>Finnish help:</b> /apua

Need help? Contact the administrators!
        """

        await update.message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


async def apua(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Show help information for users in Finnish."""
    try:
        help_text = """
🤖 <b>Vaalilakanabot - Käyttäjän komennot</b>

<b>Peruskomennot:</b>
• /start - Rekisteröi kanavan tiedotuskanavaksi
• /lakana - Näytä nykyinen vaalilakana (suomeksi)
• /sheet - Näytä nykyinen vaalilakana (englanniksi)
• /hae - Hae virkaan suomeksi (lähetä yksityisviestinä)
• /apply - Hae virkaan englanniksi (lähetä yksityisviestinä)

<b>Hauskat komennot:</b>
• /jauhis - Lähetä jauhis-tarra
• /jauh - Lähetä jauh-tarra  
• /jauho - Lähetä jauho-tarra
• /lauh - Lähetä lauh-tarra
• /mauh - Lähetä mauh-tarra

<b>Lisätietoja:</b>
• Käytä /hae yksityisviestissä hakeaksesi suomeksi
• Käytä /apply yksityisviestissä hakeaksesi englanniksi
• Vaalilakana päivittyy automaattisesti
• Vaaleilla valittujen roolien hakemukset vaativat ylläpidon hyväksynnän

<b>English help:</b> /help

Tarvitsetko apua? Ota yhteyttä ylläpitoon!
        """

        await update.message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


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


async def show_election_sheet(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Show the current election sheet in English."""
    try:
        election_sheet_text = vaalilakana_to_string_en(
            data_manager.vaalilakana, data_manager.find_division_for_position
        )
        await update.message.reply_html(
            election_sheet_text,
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
