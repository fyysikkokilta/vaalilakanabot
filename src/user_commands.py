"""User commands and basic functionality."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from .utils import vaalilakana_to_string, vaalilakana_to_string_en
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
• /applications - Show your applications
• /apply - Apply for a position (send in private chat)

<b>Fun Commands:</b>
• /jauhis - Send jauhis sticker
• /jauh - Send jauh sticker  
• /jauho - Send jauho sticker
• /lauh - Send lauh sticker
• /mauh - Send mauh sticker

<b>Additional Information:</b>
• Election sheet updates automatically
• Applications for elected positions require admin approval

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
• /hakemukset - Näytä omat hakemuksesi
• /hae - Hae virkaan (lähetä yksityisviestinä)

<b>Hauskat komennot:</b>
• /jauhis - Lähetä jauhis-tarra
• /jauh - Lähetä jauh-tarra  
• /jauho - Lähetä jauho-tarra
• /lauh - Lähetä lauh-tarra
• /mauh - Lähetä mauh-tarra

<b>Lisätietoja:</b>
• Vaalilakana päivittyy automaattisesti
• Vaaleilla valittujen roolien hakemukset vaativat ylläpidon hyväksynnän

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
            "Rekisteröity Vaalilakanabotin tiedotuskanavaksi!"
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
                "Kanava poistettu Vaalilakanabotin tiedotuskanavasta!"
            )
        else:
            await update.message.reply_text(
                "Kanavaa ei löytynyt rekisteröitynä tiedotuskanavaksi."
            )
    except Exception as e:
        logger.error(e)


def _render_applications(roles, app_rows, is_finnish: bool) -> str:
    role_by_id = {role["ID"]: role for role in roles if role.get("ID")}

    def map_status(s: str) -> str:
        match s:
            case "APPROVED":
                return "Hyväksytty" if is_finnish else "Approved"
            case "DENIED":
                return "Hylätty" if is_finnish else "Rejected"
            case "REMOVED":
                return "Poistettu" if is_finnish else "Removed"
            case "ELECTED":
                return "Valittu" if is_finnish else "Elected"
            case _:
                return "Odottaa" if is_finnish else "Pending"

    text = (
        "📋 <b>Omat hakemuksesi</b>\n\n"
        if is_finnish
        else "📋 <b>Your applications</b>\n\n"
    )
    for app in app_rows:
        r = role_by_id.get(app.get("Role_ID"), {})
        role_fi = r.get("Role_FI", app.get("Role_ID", "Tuntematon rooli"))
        role_en = r.get("Role_EN", "")
        division_fi = r.get("Division_FI", "")
        division_en = r.get("Division_EN", "")
        fiirumi = app.get("Fiirumi_Post", "")
        status = map_status(app.get("Status", ""))

        # Title
        if is_finnish:
            text += f"• <b>{role_fi}</b>\n"
        else:
            title = role_en or role_fi
            text += f"• <b>{title}</b>\n"

        # Division
        if division_fi:
            if is_finnish:
                text += f"  <b>Jaos:</b> {division_fi}\n"
            else:
                text += f"  <b>Division:</b> {division_en or division_fi}\n"

        # Status
        if is_finnish:
            text += f"  <b>Tila:</b> {status}\n"
        else:
            text += f"  <b>Status:</b> {status}\n"

        # Fiirumi link
        if fiirumi:
            label = "Fiirumi" if is_finnish else "Fiirumi"
            text += f'  <b>{label}:</b> <a href="{fiirumi}">link</a>\n'

        text += "\n"
    return text


async def applications_en(update: Update, data_manager: DataManager):
    """Show the current user's applications (English)."""
    try:
        user_id = update.effective_user.id

        # Fetch user's application rows
        app_rows = data_manager.sheets_manager.get_applications_for_user(user_id)
        if not app_rows:
            await update.message.reply_text("You have no applications yet.")
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

        app_rows = data_manager.sheets_manager.get_applications_for_user(user_id)
        if not app_rows:
            await update.message.reply_text("Sinulla ei ole vielä hakemuksia.")
            return

        roles = data_manager.get_all_roles()
        text = _render_applications(roles, app_rows, is_finnish=True)
        await update.message.reply_html(text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(e)


async def show_election_sheet(update: Update, data_manager: DataManager):
    """Show the current vaalilakana."""
    try:
        vaalilakana_text = vaalilakana_to_string(data_manager.vaalilakana)
        await update.message.reply_html(
            vaalilakana_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def show_election_sheet_en(update: Update, data_manager: DataManager):
    """Show the current election sheet in English."""
    try:
        election_sheet_text = vaalilakana_to_string_en(data_manager.vaalilakana)
        await update.message.reply_html(
            election_sheet_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def jauhis(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send jauhis sticker."""
    try:
        with open("assets/jauhis.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauhis %s", e)


async def jauh(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send jauh sticker."""
    try:
        with open("assets/jauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauh %s", e)


async def jauho(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send jauho sticker."""
    try:
        with open("assets/jauho.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauho %s", e)


async def lauh(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send lauh sticker."""
    try:
        with open("assets/lauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Lauh %s", e)


async def mauh(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send mauh sticker."""
    try:
        with open("assets/mauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Mauh %s", e)
