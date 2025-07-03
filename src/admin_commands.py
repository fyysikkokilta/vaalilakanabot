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
• /remove &lt;position&gt;, &lt;name&gt; - Remove applicant from position
• /selected &lt;position&gt;, &lt;name&gt; - Mark applicant as selected
• /pending - Show pending applications

<b>Fiirumi Link Management:</b>
• /add_fiirumi &lt;position&gt;, &lt;name&gt;, &lt;thread_id&gt; - Add Fiirumi link to applicant
• /remove_fiirumi &lt;position&gt;, &lt;name&gt; - Remove Fiirumi link from applicant

<b>Role Management:</b>
• /edit_or_add_new_role &lt;division&gt;, &lt;role&gt;, &lt;role_en&gt;, &lt;applicant_count&gt;, &lt;deadline&gt; - Edit or add role
• /remove_role &lt;division&gt;, &lt;role&gt; - Remove role

<b>Data Export:</b>
• /export_data - Export all applicant data as CSV file

<b>Examples:</b>
• /remove Puheenjohtaja, Maija Meikäläinen
• /selected Varapuheenjohtaja, Pekka Päällikkö
• /add_fiirumi Puheenjohtaja, Maija Meikäläinen, 12345
• /edit_or_add_new_role MUUT TOIMIHENKILÖT, Uusi rooli, New role, 2, 15.12.
• /remove_role MUUT TOIMIHENKILÖT, Uusi rooli
• /export_data Hovimestari

<b>Important Notes:</b>
• All commands work only in admin chat
• Thread ID can be found in Fiirumi post URL
• Deadline format: DD.MM. (e.g., 15.12.)
• <b>Division and role names support both Finnish and English</b>
• If a name is not found, the bot will show available options
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
            text = update.message.text.replace("/remove", "").strip()
            params = text.split(",")

            try:
                position = params[0].strip()
                name = params[1].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Invalid parameters - /remove <position>, <name>"
                )
                raise ValueError("Invalid parameters") from e

            # Find position by Finnish or English name
            found_position = data_manager.find_position_by_name(position)
            if not found_position:
                # Show available positions
                all_positions = data_manager.get_all_positions()
                position_list = "\n".join(
                    [f"• {pos['fi']} / {pos['en']}" for pos in all_positions[:20]]
                )  # Limit to first 20
                await update.message.reply_text(
                    f"Unknown position: {position}\n\n"
                    f"Available positions (showing first 20):\n{position_list}"
                )
                return

            division = data_manager.find_division_for_position(found_position)
            if not division:
                await update.message.reply_text(
                    f"Division not found for position: {found_position}"
                )
                return

            data_manager.remove_applicant(division, found_position, name)
            await update.message.reply_text(f"Removed:\n{found_position}: {name}")
    except Exception as e:
        logger.error(e)


async def add_fiirumi_to_applicant(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Add a fiirumi link to an applicant."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/add_fiirumi", "").strip()
            params = text.split(",")

            try:
                position = params[0].strip()
                name = params[1].strip()
                thread_id = params[2].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Invalid parameters - /add_fiirumi <position>, <name>, <thread_id>",
                )
                raise ValueError("Invalid parameters") from e

            # Find position by Finnish or English name
            found_position = data_manager.find_position_by_name(position)
            if not found_position:
                await update.message.reply_text(f"Unknown position: {position}")
                return

            if found_position not in BOARD + ELECTED_OFFICIALS:
                await update.message.reply_text(
                    f"Position {found_position} is not an elected position"
                )
                return

            if thread_id not in data_manager.fiirumi_posts:
                await update.message.reply_text(
                    f"Fiirumi post not found with given id: {thread_id}",
                )
                return

            division = data_manager.find_division_for_position(found_position)
            if not division:
                await update.message.reply_text(
                    f"Division not found for position: {found_position}"
                )
                return

            fiirumi = create_fiirumi_link(
                data_manager.fiirumi_posts[thread_id]["slug"],
                data_manager.fiirumi_posts[thread_id]["id"],
            )
            data_manager.set_applicant_fiirumi(division, found_position, name, fiirumi)

            await update.message.reply_html(
                f'Added Fiirumi:\n{found_position}: <a href="{fiirumi}">{name}</a>',
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
            params = [
                arg.strip()
                for arg in update.message.text.replace("/remove_fiirumi", "")
                .strip()
                .split(",")
            ]
            try:
                position, name = params
            except Exception as e:
                logger.error(e)
                await update.message.reply_text(
                    "Invalid parameters - /remove_fiirumi <position>, <name>"
                )
                return

            # Find position by Finnish or English name
            found_position = data_manager.find_position_by_name(position)
            if not found_position:
                await update.message.reply_text(f"Unknown position: {position}")
                return

            if found_position not in BOARD + ELECTED_OFFICIALS:
                await update.message.reply_text(
                    f"Position {found_position} is not an elected position"
                )
                return

            division = data_manager.find_division_for_position(found_position)
            if not division:
                await update.message.reply_text(
                    f"Division not found for position: {found_position}"
                )
                return

            data_manager.set_applicant_fiirumi(division, found_position, name, "")
            await update.message.reply_text(f"Fiirumi link removed:\n{name}")
    except Exception as e:
        logger.error(e)


async def add_selected_tag(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Mark an applicant as selected."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/selected", "").strip()
            params = text.split(",")

            try:
                position = params[0].strip()
                name = params[1].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Invalid parameters - /selected <position>, <name>"
                )
                raise ValueError from e

            # Find position by Finnish or English name
            found_position = data_manager.find_position_by_name(position)
            if not found_position:
                await update.message.reply_text(f"Unknown position: {position}")
                return

            division = data_manager.find_division_for_position(found_position)
            if not division:
                await update.message.reply_text(
                    f"Division not found for position: {found_position}"
                )
                return

            data_manager.set_applicant_selected(division, found_position, name)
            await update.message.reply_text(
                f"Applicant selected:\n{found_position}: {name}"
            )
    except Exception as e:
        logger.error(e)


async def edit_or_add_new_role(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Edit or add a new role."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/edit_or_add_new_role", "").strip()

            # Check if any parameters were provided
            if not text:
                await update.message.reply_text(
                    "Invalid parameters - "
                    "/edit_or_add_new_role <division>, <role>, <role_en>, <applicant_count>, <deadline>\n\n"
                    "Example: /edit_or_add_new_role MUUT TOIMIHENKILÖT, Uusi rooli, New role, 2, 15.12."
                )
                return

            params = text.split(",")

            # Validate minimum required parameters
            if len(params) < 2:
                await update.message.reply_text(
                    "Invalid parameters - need at least division and role\n"
                    "/edit_or_add_new_role <division>, <role>, <role_en>, <applicant_count>, <deadline>"
                )
                return

            try:
                division_param = params[0].strip()
                role = params[1].strip()
                role_en = (
                    params[2].strip() if len(params) > 2 and params[2].strip() else None
                )
                amount = (
                    params[3].strip() if len(params) > 3 and params[3].strip() else None
                )
                application_dl = (
                    params[4].strip() if len(params) > 4 and params[4].strip() else None
                )
            except Exception as e:
                await update.message.reply_text(
                    "Invalid parameters - "
                    "/edit_or_add_new_role <division>, <role>, <role_en>, <applicant_count>, <deadline>"
                )
                raise ValueError("Invalid parameters") from e

            # Find division by Finnish or English name
            division = data_manager.find_division_by_name(division_param)
            if not division:
                # Show available divisions
                all_divisions = data_manager.get_all_divisions()
                division_list = "\n".join(
                    [f"• {div['fi']} / {div['en']}" for div in all_divisions]
                )
                await update.message.reply_text(
                    f"Unknown division: {division_param}\n\n"
                    f"Available divisions:\n{division_list}"
                )
                return

            # Validate role name is not empty
            if not role:
                await update.message.reply_text("Role name cannot be empty.")
                return

            # Validate amount format if provided
            if amount:
                # Allow formats like: "1", "2", "1-2", "n", "13-15"
                import re

                if not re.match(r"^(\d+(-\d+)?|n)$", amount):
                    await update.message.reply_text(
                        f"Invalid applicant count: {amount}\n"
                        "Allowed formats: '1', '2', '1-2', 'n', '13-15'"
                    )
                    return

            # Validate application deadline format if provided
            if application_dl:
                # Allow formats like: "15.12.", "3.11.", "29.11."
                import re

                if not re.match(r"^\d{1,2}\.\d{1,2}\.$", application_dl):
                    await update.message.reply_text(
                        f"Invalid deadline: {application_dl}\n"
                        "Allowed format: 'DD.MM.' (e.g., '15.12.', '3.11.')"
                    )
                    return

            # Check if role already exists
            existing_roles = [
                role_data["title"]
                for role_data in data_manager.vaalilakana[division]["roles"].values()
            ]

            if role not in existing_roles:
                # Add new role
                data_manager.vaalilakana[division]["roles"][role] = {
                    "title": role,
                    "title_en": role_en if role_en else role,
                    "amount": amount,
                    "application_dl": application_dl,
                    "applicants": [],
                }

                # Update positions list
                data_manager.positions.append(
                    {"fi": role, "en": role_en if role_en else role}
                )

                data_manager.save_data(
                    "data/vaalilakana.json", data_manager.vaalilakana
                )
                await update.message.reply_text(
                    f"✅ Added new role:\n"
                    f"<b>Division:</b> {division}\n"
                    f"<b>Role:</b> {role}\n"
                    f"<b>Role (EN):</b> {role_en if role_en else role}\n"
                    f"<b>Deadline:</b> {application_dl if application_dl else 'not set'}",
                    parse_mode="HTML",
                )
            else:
                # Update existing role
                # Preserve existing applicants
                existing_applicants = data_manager.vaalilakana[division]["roles"][role][
                    "applicants"
                ]

                data_manager.vaalilakana[division]["roles"][role] = {
                    "title": role,
                    "title_en": role_en if role_en else role,
                    "amount": amount,
                    "application_dl": application_dl,
                    "applicants": existing_applicants,
                }

                data_manager.save_data(
                    "data/vaalilakana.json", data_manager.vaalilakana
                )
                await update.message.reply_text(
                    f"✅ Updated role:\n"
                    f"<b>Division:</b> {division}\n"
                    f"<b>Role:</b> {role}\n"
                    f"<b>Role (EN):</b> {role_en if role_en else role}\n"
                    f"<b>Applicant count:</b> {amount if amount else 'not set'}\n"
                    f"<b>Deadline:</b> {application_dl if application_dl else 'not set'}\n"
                    f"<b>Applicants:</b> {len(existing_applicants)}",
                    parse_mode="HTML",
                )
    except Exception as e:
        logger.error(f"Error in edit_or_add_new_role: {e}")
        await update.message.reply_text(
            "Error in role editing. Check parameters and try again."
        )


async def remove_role(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Remove a role."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/remove_role", "").strip()
            params = text.split(",")

            try:
                division_param = params[0].strip()
                role_param = params[1].strip()
            except Exception as e:
                await update.message.reply_text(
                    "Invalid parameters - /remove_role <division>, <role>"
                )
                raise ValueError("Invalid parameters") from e

            # Find division by Finnish or English name
            division = data_manager.find_division_by_name(division_param)
            if not division:
                all_divisions = data_manager.get_all_divisions()
                division_list = "\n".join(
                    [f"• {div['fi']} / {div['en']}" for div in all_divisions]
                )
                await update.message.reply_text(
                    f"Unknown division: {division_param}\n\n"
                    f"Available divisions:\n{division_list}"
                )
                return

            # Find role by Finnish or English name
            role = data_manager.find_position_by_name(role_param, division)
            if not role:
                # Show available roles in this division
                division_roles = []
                for role_title, role_data in data_manager.vaalilakana[division][
                    "roles"
                ].items():
                    division_roles.append(
                        f"• {role_title} / {role_data.get('title_en', role_title)}"
                    )
                role_list = "\n".join(division_roles[:20])  # Limit to first 20
                await update.message.reply_text(
                    f"Unknown role: {role_param}\n\n"
                    f"Available roles in {division} (showing first 20):\n{role_list}"
                )
                return

            del data_manager.vaalilakana[division]["roles"][role]
            # Remove from positions list
            data_manager.positions = [
                pos for pos in data_manager.positions if pos["fi"] != role
            ]
            data_manager.save_data("data/vaalilakana.json", data_manager.vaalilakana)
            await update.message.reply_text(f"Removed:\n{division}: {role}")
    except Exception as e:
        logger.error(e)


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Export applicant data to CSV."""
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace("/export_data", "").strip()
            params = text.split(",")

            output = StringIO()
            output.write("Name,Role,Email,Telegram\n")

            if len(text) > 0:
                position_param = params[0].strip()
                # Find position by Finnish or English name
                found_position = data_manager.find_position_by_name(position_param)
                if not found_position:
                    await update.message.reply_text(
                        f"Unknown position: {position_param}"
                    )
                    return

                division = data_manager.find_division_for_position(found_position)
                if division:
                    for applicant in data_manager.vaalilakana[division]["roles"][
                        found_position
                    ]["applicants"]:
                        output.write(
                            f"{applicant['name']},{found_position},{applicant['email']},{applicant['telegram']}\n"
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
