"""Admin commands and operations."""

import logging
from io import StringIO

from telegram import Update
from telegram.ext import ContextTypes

from .config import ADMIN_CHAT_ID, BOARD, ELECTED_OFFICIALS
from .utils import create_fiirumi_link

logger = logging.getLogger("vaalilakanabot")


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Show help information for admins in English."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            help_text = """
🔧 <b>Vaalilakanabot - Admin Commands</b>

<b>Applicant Management:</b>
• /poista &lt;position&gt;, &lt;name&gt; - Remove applicant from position
• /valittu &lt;position&gt;, &lt;name&gt; - Mark applicant as selected
• /odottavat - Show pending applications

<b>Fiirumi Link Management:</b>
• /lisaa_fiirumi &lt;position&gt;, &lt;name&gt;, &lt;thread_id&gt; - Add Fiirumi link to applicant
• /poista_fiirumi &lt;position&gt;, &lt;name&gt; - Remove Fiirumi link from applicant

<b>Role Management:</b>
• /muokkaa_roolia &lt;division&gt;, &lt;role&gt;, &lt;role_en&gt;, &lt;applicant_count&gt;, &lt;deadline&gt; - Edit or add role
• /poista_rooli &lt;division&gt;, &lt;role&gt; - Remove role

<b>Data Export:</b>
• /vie_tiedot - Export all applicant data as CSV file

<b>Examples:</b>
• /poista Puheenjohtaja, Maija Meikäläinen
• /valittu Varapuheenjohtaja, Pekka Päällikkö
• /lisaa_fiirumi Puheenjohtaja, Maija Meikäläinen, 12345
• /muokkaa_roolia MUUT TOIMIHENKILÖT, Uusi rooli, New role, 2, 15.12.
• /poista_rooli MUUT TOIMIHENKILÖT, Uusi rooli
• /vie_tiedot Hovimestari

<b>Important Notes:</b>
• All commands work only in admin chat
• Thread ID can be found in Fiirumi post URL
• Deadline format: DD.MM. (e.g., 15.12.)
            """

            await update.message.reply_html(help_text)
    except Exception as e:
        logger.error(e)


async def remove_applicant(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Remove an applicant from a position."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/poista", "").strip()
            params = text.split(",")

            try:
                position = params[0].strip()
                name = params[1].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Virheelliset parametrit - /poista <virka>, <nimi>"
                )
                raise ValueError("Invalid parameters") from e

            if position not in [position["fi"] for position in data_manager.positions]:
                await update.message.reply_text(f"Tunnistamaton virka: {position}")
                raise ValueError(f"Unknown position {position}")

            division = data_manager.find_division_for_position(position)
            if not division:
                await update.message.reply_text(f"Jaosta ei löytynyt: {position}")
                return

            data_manager.remove_applicant(division, position, name)
            await update.message.reply_text(f"Poistettu:\n{position}: {name}")
    except Exception as e:
        logger.error(e)


async def add_fiirumi_to_applicant(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Add a fiirumi link to an applicant."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/lisaa_fiirumi", "").strip()
            params = text.split(",")

            try:
                position = params[0].strip()
                name = params[1].strip()
                thread_id = params[2].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Virheelliset parametrit - /lisaa_fiirumi <virka>, <nimi>, <thread id>",
                )
                raise ValueError("Invalid parameters") from e

            if position not in BOARD + ELECTED_OFFICIALS:
                await update.message.reply_text(f"Tunnistamaton virka: {position}")
                raise ValueError(f"Unknown position {position}")

            if thread_id not in data_manager.fiirumi_posts:
                await update.message.reply_text(
                    f"Fiirumi-postausta ei löytynyt annetulla id:llä: {thread_id}",
                )
                raise ValueError(f"Unknown thread {thread_id}")

            division = data_manager.find_division_for_position(position)
            if not division:
                await update.message.reply_text(f"Jaosta ei löytynyt: {position}")
                return

            fiirumi = create_fiirumi_link(
                data_manager.fiirumi_posts[thread_id]["slug"],
                data_manager.fiirumi_posts[thread_id]["id"],
            )
            data_manager.set_applicant_fiirumi(division, position, name, fiirumi)

            await update.message.reply_html(
                f'Lisätty Fiirumi:\n{position}: <a href="{fiirumi}">{name}</a>',
            )
    except Exception as e:
        logger.error(e)


async def unassociate_fiirumi(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Remove fiirumi link from an applicant."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            # Converts /poista_fiirumi Puheenjohtaja, Fysisti kiltalainen
            # to ["Puheenjohtaja", "Fysisti kiltalainen"]
            params = [
                arg.strip()
                for arg in update.message.text.replace("/poista_fiirumi", "")
                .strip()
                .split(",")
            ]
            # Try find role
            try:
                position, name = params
            except Exception as e:
                logger.error(e)
                await update.message.reply_text(
                    "Virheelliset parametrit - /poista_fiirumi <virka>, <nimi>"
                )
                return

            if position not in BOARD + ELECTED_OFFICIALS:
                await update.message.reply_text(
                    "Virheelliset parametrit, roolia ei löytynyt"
                )
                return

            # Try finding the dict with matching applicant name from vaalilakana
            division = data_manager.find_division_for_position(position)
            if not division:
                await update.message.reply_text(f"Jaosta ei löytynyt: {position}")
                return

            data_manager.set_applicant_fiirumi(division, position, name, "")
            await update.message.reply_text(f"Fiirumi linkki poistettu:\n{name}")
        else:
            # Not admin chat
            pass
    except Exception as e:
        # Unknown error :/
        logger.error(e)


async def add_selected_tag(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Mark an applicant as selected."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/valittu", "").strip()
            params = text.split(",")

            try:
                position = params[0].strip()
                name = params[1].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Virheelliset parametrit - /valittu <virka>, <nimi>"
                )
                raise ValueError from e

            if position not in [position["fi"] for position in data_manager.positions]:
                await update.message.reply_text(f"Tunnistamaton virka: {position}")
                raise ValueError(f"Unknown position {position}")

            division = data_manager.find_division_for_position(position)
            if not division:
                await update.message.reply_text(f"Jaosta ei löytynyt: {position}")
                return

            data_manager.set_applicant_selected(division, position, name)
            await update.message.reply_text(f"Hakija valittu:\n{position}: {name}")
    except Exception as e:
        logger.error(e)


async def edit_or_add_new_role(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Edit or add a new role."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/muokkaa_roolia", "").strip()
            params = text.split(",")

            try:
                division = params[0].strip()
                role = params[1].strip()
                role_en = params[2].strip() if params[2].strip() else None
                amount = params[3].strip() if params[3].strip() else None
                application_dl = params[4].strip() if params[4].strip() else None
            except Exception as e:
                await update.message.reply_text(
                    "Virheelliset parametrit - "
                    "/muokkaa_roolia <jaos>, <rooli>, <rooli_en>, <hakijamäärä>, <hakuaika>"
                )
                raise ValueError("Invalid parameters") from e

            if division not in [division["fi"] for division in data_manager.divisions]:
                await update.message.reply_text(f"Tunnistamaton jaos: {division}")
                raise ValueError(f"Unknown division {division}")

            if role not in [
                role["title"]
                for role in data_manager.vaalilakana[division]["roles"].values()
            ]:
                data_manager.vaalilakana[division]["roles"][role] = {
                    "title": role,
                    "title_en": role_en if role_en else role,
                    "amount": amount,
                    "application_dl": application_dl,
                    "applicants": [],
                }
                data_manager.positions.append({"fi": role, "en": role_en})
                data_manager.save_data(
                    "data/vaalilakana.json", data_manager.vaalilakana
                )
                await update.message.reply_text(f"Lisätty:\n{division}: {role}")
            else:
                data_manager.vaalilakana[division]["roles"][role] = {
                    "title": role,
                    "title_en": role_en if role_en else role,
                    "amount": amount,
                    "application_dl": application_dl,
                    "applicants": data_manager.vaalilakana[division]["roles"][role][
                        "applicants"
                    ],
                }
                data_manager.save_data(
                    "data/vaalilakana.json", data_manager.vaalilakana
                )
                await update.message.reply_text(f"Päivitetty:\n{division}: {role}")
    except Exception as e:
        logger.error(e)


async def remove_role(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Remove a role."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/poista_rooli", "").strip()
            params = text.split(",")

            try:
                division = params[0].strip()
                role = params[1].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Virheelliset parametrit - /poista_rooli <jaos>, <rooli>"
                )
                raise ValueError("Invalid parameters") from e

            if division not in [division["fi"] for division in data_manager.divisions]:
                await update.message.reply_text(f"Tunnistamaton jaos: {division}")
                raise ValueError(f"Unknown division {division}")

            if role not in [
                role["title"]
                for role in data_manager.vaalilakana[division]["roles"].values()
            ]:
                await update.message.reply_text(f"Tunnistamaton virka: {role}")
                raise ValueError(f"Unknown position {role}")

            del data_manager.vaalilakana[division]["roles"][role]
            data_manager.positions.remove({"fi": role, "en": role})
            data_manager.save_data("data/vaalilakana.json", data_manager.vaalilakana)
            await update.message.reply_text(f"Poistettu:\n{division}: {role}")
    except Exception as e:
        logger.error(e)


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Export applicant data to CSV."""
    # Create a csv with the name, role, email and telegram of all applicants
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/vie_tiedot", "").strip()
            params = text.split(",")

            output = StringIO()
            output.write("Name,Role,Email,Telegram\n")

            if len(text) > 0:
                role = params[0].strip()
                if role not in [position["fi"] for position in data_manager.positions]:
                    await update.message.reply_text(f"Tunnistamaton virka: {role}")
                    raise ValueError(f"Unknown position {role}")

                division = data_manager.find_division_for_position(role)
                if division:
                    for applicant in data_manager.vaalilakana[division]["roles"][role][
                        "applicants"
                    ]:
                        output.write(
                            f"{applicant['name']},{role},{applicant['email']},{applicant['telegram']}\n"
                        )
            else:
                for division in data_manager.vaalilakana.values():
                    for role in division["roles"].values():
                        for applicant in role["applicants"]:
                            output.write(
                                f"{applicant['name']},{role['title']},{applicant['email']},{applicant['telegram']}\n"
                            )
            output.seek(0)
            await update.message.reply_document(output, filename="applicants.csv")
    except Exception as e:
        logger.error(e)
