"""User commands and basic functionality."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from .utils import (
    vaalilakana_to_string,
    send_sticker,
    map_application_status,
    get_translation,
)
from .sheets_data_manager import DataManager

logger = logging.getLogger("vaalilakanabot")


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Show help information for users in English."""
    try:
        help_text = """
🤖 <b>Vaalilakanabot - User Commands</b>

<b>Basic Commands:</b>
• /start - Register channel for announcements
• /stop - Unregister channel for announcements
• /sheet - Show current election sheet
• /applications - Show your applications (private chat)
• /register - Register or update your info (private chat, English)
• /apply - Apply for a position (private chat)

<b>Fun Commands:</b>
• /jauhis - Send jauhis sticker
• /jauh - Send jauh sticker  
• /jauho - Send jauho sticker
• /lauh - Send lauh sticker
• /mauh - Send mauh sticker
• /yauh - Send yauh sticker

<b>Registration and applying (private message):</b>
1) <b>Register first:</b> Use /register (or /rekisteröidy for Finnish). Enter your name, email, and consent. You can run it again to update your info.
2) Applications are linked to your Telegram user—only apply from your own device.
3) Official roles are in divisions. Find them on the physical sheet in the guild room or on Fiirumi in the "vaalilakana" section.
4) Use /apply and follow the bot. You can check your details before submitting.
5) For elected roles, remember to post an introduction on Fiirumi.

<b>After applying:</b>
• Check status with /applications
• To cancel, contact the board.

<b>Finnish help:</b> /apua

Need help? Contact the board!
        """

        await update.message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


async def apua_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Show help information for users in Finnish."""
    try:
        help_text = """
🤖 <b>Vaalilakanabot - Käyttäjän komennot</b>

<b>Peruskomennot:</b>
• /start - Rekisteröi kanavan tiedotuskanavaksi
• /stop - Poista kanava tiedotuskanavista
• /lakana - Näytä nykyinen vaalilakana
• /hakemukset - Näytä omat hakemuksesi (yksityisviesti)
• /rekisteröidy - Rekisteröidy tai päivitä tietosi (yksityisviesti)
• /hae - Hae virkaan (yksityisviesti)

<b>Hauskat komennot:</b>
• /jauhis - Lähetä jauhis-tarra
• /jauh - Lähetä jauh-tarra  
• /jauho - Lähetä jauho-tarra
• /lauh - Lähetä lauh-tarra
• /mauh - Lähetä mauh-tarra
• /yauh - Lähetä yauh-tarra

<b>Rekisteröityminen ja hakeminen (yksityisviesti):</b>
1) <b>Rekisteröidy ensin:</b> Käytä /rekisteröidy (tai /register englanniksi). Syötä nimesi, sähköposti ja suostumus. Voit ajaa komennon uudelleen päivittääksesi tiedot.
2) Hakemukset yhdistetään telegramkäyttäjääsi—hakekaa vain omalla laitteella.
3) Toimariroolit on jaettu jaoksittain. Etsi rooli kiltiksen fyysisestä vaalilakanasta tai Fiirumilta vaalilakanaosiosta.
4) Aloita hakeminen komennolla /hae ja seuraa botin ohjeita. Voit tarkistaa tiedot ennen lähettämistä.
5) Vaaleilla valittavaan rooliin haettaessa muista tehdä esittelyteksti Fiirumilla.

<b>Hakemisen jälkeen:</b>
• Tarkista tilanne komennolla /hakemukset
• Peruuttaaksesi hakemuksen, ota yhteyttä raatiin.

<b>English help:</b> /help

Tarvitsetko apua? Ota yhteyttä raatiin!
        """

        await update.message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


async def register_channel(update: Update, data_manager: DataManager):
    """Register a channel for announcements."""
    try:
        chat_id = update.message.chat.id
        data_manager.add_channel(chat_id)
        await update.message.reply_text(
            "Registered as Vaalilakanabot announcement channel!"
        )
    except Exception as e:
        logger.error(e)


async def unregister_channel(update: Update, data_manager: DataManager):
    """Unregister a channel from announcements."""
    try:
        chat_id = update.message.chat.id
        removed = data_manager.remove_channel(chat_id)
        if removed:
            await update.message.reply_text(
                "Channel removed from Vaalilakanabot announcement channels!"
            )
        else:
            await update.message.reply_text(
                "Channel not found in registered announcement channels."
            )
    except Exception as e:
        logger.error(e)


def _render_applications(roles, app_rows, is_finnish: bool) -> str:
    role_by_id = {role.get("ID"): role for role in roles if role.get("ID")}

    text = get_translation("my_applications", is_finnish)
    for app in app_rows:
        r = role_by_id.get(app.get("Role_ID"), {})
        role_fi = r.get("Role_FI", app.get("Role_ID", "Tuntematon rooli"))
        role_en = r.get("Role_EN", "")
        division_fi = r.get("Division_FI", "")
        division_en = r.get("Division_EN", "")
        fiirumi = app.get("Fiirumi_Post", "")
        status = map_application_status(app.get("Status", "PENDING"), is_finnish)

        # Title
        if is_finnish:
            text += f"• <b>{role_fi}</b>\n"
        else:
            title = role_en or role_fi
            text += f"• <b>{title}</b>\n"

        # Division
        if division_fi:
            division_label = get_translation("division_label", is_finnish)
            division_name = division_fi if is_finnish else (division_en or division_fi)
            text += f"  <b>{division_label}:</b> {division_name}\n"

        # Status
        status_label = get_translation("status_label", is_finnish)
        text += f"  <b>{status_label}:</b> {status}\n"

        # Fiirumi link
        if fiirumi:
            fiirumi_label = get_translation("fiirumi_label", is_finnish)
            text += f'  <b>{fiirumi_label}:</b> <a href="{fiirumi}">link</a>\n'

        text += "\n"
    return text


async def applications_en(update: Update, data_manager: DataManager):
    """Show the current user's applications (English)."""
    try:
        user_id = update.effective_user.id
        if not data_manager.sheets_manager.get_user_by_telegram_id(user_id):
            await update.message.reply_text(
                get_translation("please_register_first", is_finnish=False)
            )
            return

        # Fetch user's application rows
        app_rows = data_manager.get_applications_for_user(user_id)
        if not app_rows:
            await update.message.reply_text(
                get_translation("no_applications", is_finnish=False)
            )
            return

        roles = data_manager.get_all_roles()
        text = _render_applications(roles, app_rows, is_finnish=False)
        await update.message.reply_html(text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(e)


async def applications(update: Update, data_manager: DataManager):
    """Näytä käyttäjän omat hakemukset (suomeksi)."""
    try:
        user_id = update.effective_user.id
        if not data_manager.sheets_manager.get_user_by_telegram_id(user_id):
            await update.message.reply_text(
                get_translation("please_register_first", is_finnish=True)
            )
            return

        app_rows = data_manager.get_applications_for_user(user_id)
        if not app_rows:
            await update.message.reply_text(
                get_translation("no_applications", is_finnish=True)
            )
            return

        roles = data_manager.get_all_roles()
        text = _render_applications(roles, app_rows, is_finnish=True)
        await update.message.reply_html(text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(e)


async def show_election_sheet(update: Update, data_manager: DataManager):
    """Show the current vaalilakana."""
    try:
        vaalilakana_text = vaalilakana_to_string(data_manager.vaalilakana, "fi")
        await update.message.reply_html(
            vaalilakana_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def show_election_sheet_en(update: Update, data_manager: DataManager):
    """Show the current election sheet in English."""
    try:
        election_sheet_text = vaalilakana_to_string(data_manager.vaalilakana, "en")
        await update.message.reply_html(
            election_sheet_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def jauhis(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send jauhis sticker."""
    await send_sticker(update, "jauhis")


async def jauh(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send jauh sticker."""
    await send_sticker(update, "jauh")


async def jauho(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send jauho sticker."""
    await send_sticker(update, "jauho")


async def lauh(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send lauh sticker."""
    await send_sticker(update, "lauh")


async def mauh(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send mauh sticker."""
    await send_sticker(update, "mauh")


async def yauh(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send yauh sticker."""
    await send_sticker(update, "yauh")
