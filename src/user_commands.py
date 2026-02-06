"""User commands and basic functionality."""

import logging
from typing import Dict, List, Union

from telegram import Update
from telegram.ext import ContextTypes

from .types import ApplicationRow, ElectionStructureRow
from .utils import (
    vaalilakana_to_string,
    send_sticker,
    map_application_status,
    get_translation,
)
from .sheets_data_manager import DataManager

logger = logging.getLogger("vaalilakanabot")


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information for users in English."""
    message = update.message
    if message is None:
        return
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

        await message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


async def apua_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information for users in Finnish."""
    message = update.message
    if message is None:
        return
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

        await message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


async def register_channel(update: Update, data_manager: DataManager) -> None:
    """Register a channel for announcements."""
    message = update.message
    if message is None:
        return
    try:
        chat_id = message.chat.id
        data_manager.add_channel(chat_id)
        await message.reply_text(
            "Registered as Vaalilakanabot announcement channel!"
        )
    except Exception as e:
        logger.error(e)


async def unregister_channel(update: Update, data_manager: DataManager) -> None:
    """Unregister a channel from announcements."""
    message = update.message
    if message is None:
        return
    try:
        chat_id = message.chat.id
        removed = data_manager.remove_channel(chat_id)
        if removed:
            await message.reply_text(
                "Channel removed from Vaalilakanabot announcement channels!"
            )
        else:
            await message.reply_text(
                "Channel not found in registered announcement channels."
            )
    except Exception as e:
        logger.error(e)


def _format_one_application(
    app: ApplicationRow,
    role_data: Union[Dict[str, object], ElectionStructureRow],
    is_finnish: bool,
) -> str:
    """Format a single application block for display."""
    role_fi = role_data.get("Role_FI", app.get("Role_ID", "Tuntematon rooli"))
    role_en = role_data.get("Role_EN", "")
    division_fi = role_data.get("Division_FI", "")
    division_en = role_data.get("Division_EN", "")
    status = map_application_status(app.get("Status", "PENDING"), is_finnish)
    block = f"• <b>{role_fi if is_finnish else (role_en or role_fi)}</b>\n"
    if division_fi:
        div_label = get_translation("division_label", is_finnish)
        div_name = division_fi if is_finnish else (division_en or division_fi)
        block += f"  <b>{div_label}:</b> {div_name}\n"
    block += f"  <b>{get_translation('status_label', is_finnish)}:</b> {status}\n"
    fiirumi = app.get("Fiirumi_Post", "")
    if fiirumi:
        block += f'  <b>{get_translation("fiirumi_label", is_finnish)}:</b> <a href="{fiirumi}">link</a>\n'
    return block + "\n"


def _render_applications(
    roles: List[ElectionStructureRow],
    app_rows: List[ApplicationRow],
    is_finnish: bool,
) -> str:
    role_by_id: Dict[str, ElectionStructureRow] = {
        role.get("ID", ""): role for role in roles if role.get("ID")
    }
    text = get_translation("my_applications", is_finnish)
    empty_role: Dict[str, object] = {}
    for app in app_rows:
        r = role_by_id.get(app.get("Role_ID", ""), empty_role)
        text += _format_one_application(app, r, is_finnish)
    return text


async def applications_en(update: Update, data_manager: DataManager) -> None:
    """Show the current user's applications (English)."""
    message = update.message
    if message is None or update.effective_user is None:
        return
    try:
        user_id = update.effective_user.id
        if not data_manager.get_user_by_telegram_id(user_id):
            await message.reply_text(
                get_translation("please_register_first", is_finnish=False)
            )
            return

        # Fetch user's application rows
        app_rows = data_manager.get_applications_for_user(user_id)
        if not app_rows:
            await message.reply_text(
                get_translation("no_applications", is_finnish=False)
            )
            return

        roles = data_manager.get_all_roles()
        text = _render_applications(roles, app_rows, is_finnish=False)
        await message.reply_html(text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(e)


async def applications(update: Update, data_manager: DataManager) -> None:
    """Näytä käyttäjän omat hakemukset (suomeksi)."""
    message = update.message
    if message is None or update.effective_user is None:
        return
    try:
        user_id = update.effective_user.id
        if not data_manager.get_user_by_telegram_id(user_id):
            await message.reply_text(
                get_translation("please_register_first", is_finnish=True)
            )
            return

        app_rows = data_manager.get_applications_for_user(user_id)
        if not app_rows:
            await message.reply_text(
                get_translation("no_applications", is_finnish=True)
            )
            return

        roles = data_manager.get_all_roles()
        text = _render_applications(roles, app_rows, is_finnish=True)
        await message.reply_html(text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(e)


async def show_election_sheet(update: Update, data_manager: DataManager) -> None:
    """Show the current vaalilakana."""
    if update.message is None:
        return
    try:
        vaalilakana_text = vaalilakana_to_string(data_manager.vaalilakana, "fi")
        await update.message.reply_html(
            vaalilakana_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def show_election_sheet_en(update: Update, data_manager: DataManager) -> None:
    """Show the current election sheet in English."""
    message = update.message
    if message is None:
        return
    try:
        election_sheet_text = vaalilakana_to_string(data_manager.vaalilakana, "en")
        await message.reply_html(
            election_sheet_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def jauhis(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send jauhis sticker."""
    await send_sticker(update, "jauhis")


async def jauh(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send jauh sticker."""
    await send_sticker(update, "jauh")


async def jauho(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send jauho sticker."""
    await send_sticker(update, "jauho")


async def lauh(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send lauh sticker."""
    await send_sticker(update, "lauh")


async def mauh(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send mauh sticker."""
    await send_sticker(update, "mauh")


async def yauh(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send yauh sticker."""
    await send_sticker(update, "yauh")
