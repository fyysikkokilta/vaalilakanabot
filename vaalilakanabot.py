from io import StringIO
import json
import os
import sys
import time

import logging
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
)

from lakanaupdater import update_election_sheet
from createvaalilakana import create_vaalilakana

TOKEN = os.environ["VAALILAKANABOT_TOKEN"]
ADMIN_CHAT_ID = os.environ["ADMIN_CHAT_ID"]
BASE_URL = os.environ["BASE_URL"]

TOPIC_LIST_URL = os.environ["TOPIC_LIST_URL"]
QUESTION_LIST_URL = os.environ["QUESTION_LIST_URL"]

# Election positions
BOARD = os.environ["BOARD"].split(",")
ELECTED_OFFICIALS = os.environ["ELECTED_OFFICIALS"].split(",")

SELECTING_LANGUAGE = "SELECTING_LANGUAGE"
SELECTING_DIVISION = "SELECTING_DIVISION"
SELECTING_ROLE = "SELECTING_ROLE"
GIVING_NAME = "GIVING_NAME"
GIVING_EMAIL = "GIVING_EMAIL"
CONFIRMING_APPLICATION = "CONFIRMING_APPLICATION"

channels = []
vaalilakana = {}
positions = []
divisions = []
fiirumi_posts = []
question_posts = []

logger = logging.getLogger("vaalilakanabot")
logger.setLevel(logging.INFO)

fh = logging.StreamHandler(sys.stdout)
fh.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

try:
    with open("data/vaalilakana.json", "r") as f:
        data = f.read()
        vaalilakana = json.loads(data)
        positions = [
            {"fi": role["title"], "en": role["title_en"]}
            for division in vaalilakana.values()
            for role in division["roles"].values()
        ]
        divisions = [
            {"fi": division["division"], "en": division["division_en"]}
            for division in vaalilakana.values()
        ]
except FileNotFoundError:
    vaalilakana = create_vaalilakana()
    positions = [
        {"fi": role["title"], "en": role["title_en"]}
        for division in vaalilakana.values()
        for role in division["roles"].values()
    ]
    divisions = [
        {"fi": division["division"], "en": division["division_en"]}
        for division in vaalilakana.values()
    ]

logger.info("Loaded vaalilakana: %s", vaalilakana)

try:
    with open("data/channels.json", "r") as f:
        data = f.read()
        channels = json.loads(data)
except FileNotFoundError:
    channels = []

logger.info("Loaded channels: %s", channels)

try:
    with open("data/fiirumi_posts.json", "r") as f:
        data = f.read()
        fiirumi_posts = json.loads(data)
except FileNotFoundError:
    fiirumi_posts = {}

logger.info("Loaded fiirumi posts: %s", fiirumi_posts)

try:
    with open("data/question_posts.json", "r") as f:
        data = f.read()
        question_posts = json.loads(data)
except FileNotFoundError:
    question_posts = {}

logger.info("Loaded question posts: %s", question_posts)


def _save_data(filename, content):
    with open(filename, "w+") as fp:
        fp.write(json.dumps(content))


def _find_division_for_position(position):
    for division in vaalilakana.values():
        if position in division["roles"]:
            return division["division"]

    logger.warning("Position %s not found in vaalilakana", position)
    return None


def _vaalilakana_to_string():
    output = ""
    output += "<b>---------------Raati---------------</b>\n"
    # Hardcoded to maintain order instead using dict keys
    for position in BOARD:
        output += f"<b>{position}:</b>\n"
        division = _find_division_for_position(position)
        applicants = vaalilakana[division]["roles"][position]["applicants"]
        for applicant in applicants:
            link = applicant["fiirumi"]
            selected = applicant["valittu"]
            if selected:
                if link:
                    output += f'- <a href="{link}">{applicant["name"]}</a> (valittu)\n'
                else:
                    output += f'- {applicant["name"]} (valittu)\n'
            else:
                if link:
                    output += f'- <a href="{link}">{applicant["name"]}</a>\n'
                else:
                    output += f'- {applicant["name"]}\n'

        output += "\n"
    output += "<b>----------Toimihenkilöt----------</b>\n"
    for position in ELECTED_OFFICIALS:
        output += f"<b>{position}:</b>\n"
        division = _find_division_for_position(position)
        applicants = vaalilakana[division]["roles"][position]["applicants"]
        for applicant in applicants:
            link = applicant["fiirumi"]
            selected = applicant["valittu"]
            if selected:
                if link:
                    output += f'- <a href="{link}">{applicant["name"]}</a> (valittu)\n'
                else:
                    output += f'- {applicant["name"]} (valittu)\n'
            else:
                if link:
                    output += f'- <a href="{link}">{applicant["name"]}</a>\n'
                else:
                    output += f'- {applicant["name"]}\n'

        output += "\n"
    return output


async def _announce_to_channels(message: str, context: ContextTypes.DEFAULT_TYPE):
    for cid in channels:
        try:
            await context.bot.send_message(cid, message, parse_mode="HTML")
            time.sleep(0.5)
        except Exception as e:
            logger.error(e)
            channels.remove(cid)
            _save_data("data/channels.json", channels)
            continue


def _generate_keyboard(options, callback_data=None, back=None):
    keyboard = []
    for option in options:
        if callback_data:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        option, callback_data=callback_data[options.index(option)]
                    )
                ]
            )
        else:
            keyboard.append([InlineKeyboardButton(option, callback_data=option)])

    if back:
        keyboard.insert(0, [InlineKeyboardButton(back, callback_data="back")])
    return keyboard


async def parse_fiirumi_posts(context: ContextTypes.DEFAULT_TYPE):
    try:
        page_fiirumi = requests.get(TOPIC_LIST_URL, timeout=10)
        logger.debug(page_fiirumi)
        page_question = requests.get(QUESTION_LIST_URL, timeout=10)
        topic_list_raw = page_fiirumi.json()
        logger.debug(str(topic_list_raw))
        question_list_raw = page_question.json()
        topic_list = topic_list_raw["topic_list"]["topics"]
        question_list = question_list_raw["topic_list"]["topics"]

        logger.debug(topic_list)
    except KeyError as e:
        logger.error(
            "The topic and question lists cannot be found. Check URLs. Got error %s", e
        )
        return
    except Exception as e:
        logger.error(e)
        return

    for topic in topic_list:
        t_id = topic["id"]
        title = topic["title"]
        slug = topic["slug"]
        if str(t_id) not in fiirumi_posts:
            new_post = {
                "id": t_id,
                "title": title,
                "slug": slug,
            }
            fiirumi_posts[str(t_id)] = new_post
            _save_data("data/fiirumi_posts.json", fiirumi_posts)
            await _announce_to_channels(
                f"<b>Uusi postaus Vaalipeli-palstalla!</b>\n{title}\n{BASE_URL}/t/{slug}/{t_id}",
                context,
            )

    for question in question_list:
        t_id = question["id"]
        title = question["title"]
        slug = question["slug"]
        posts_count = question["posts_count"]
        if str(t_id) not in question_posts:
            new_question = {
                "id": t_id,
                "title": title,
                "slug": slug,
                "posts_count": posts_count,
            }
            question_posts[str(t_id)] = new_question
            _save_data("data/question_posts.json", question_posts)
            await _announce_to_channels(
                f"<b>Uusi kysymys Fiirumilla!</b>\n{title}\n{BASE_URL}/t/{slug}/{t_id}",
                context,
            )

        else:
            has_new_posts = posts_count > question_posts[str(t_id)]["posts_count"]
            question_posts[str(t_id)]["posts_count"] = posts_count
            _save_data("data/question_posts.json", question_posts)
            if has_new_posts:
                last_poster = question["last_poster_username"]
                announcement = (
                    f"<b>Uusia vastauksia Fiirumilla!</b>\n"
                    f"{title}\n{BASE_URL}/t/{slug}/{t_id}/{posts_count}\n"
                    f"Viimeisin vastaaja: {last_poster}"
                )
                await _announce_to_channels(announcement, context)


async def remove_applicant(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            if position not in [position["fi"] for position in positions]:
                await update.message.reply_text(f"Tunnistamaton virka: {position}")
                raise ValueError(f"Unknown position {position}")

            found = None
            division = _find_division_for_position(position)
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                if name == applicant["name"]:
                    found = applicant
                    break

            if not found:
                await update.message.reply_text(f"Hakijaa ei löydy: {name}")
                raise ValueError(f"Applicant not found: {name}")

            vaalilakana[division]["roles"][position]["applicants"].remove(found)
            _save_data("data/vaalilakana.json", vaalilakana)

            await update.message.reply_text(f"Poistettu:\n{position}: {name}")
    except Exception as e:
        logger.error(e)


async def add_fiirumi_to_applicant(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            if thread_id not in fiirumi_posts:
                await update.message.reply_text(
                    f"Fiirumi-postausta ei löytynyt annetulla id:llä: {thread_id}",
                )
                raise ValueError(f"Unknown thread {thread_id}")

            found = False

            division = _find_division_for_position(position)
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                if name == applicant["name"]:
                    found = True
                    fiirumi = f'{BASE_URL}/t/{fiirumi_posts[thread_id]["slug"]}/{fiirumi_posts[thread_id]["id"]}'
                    applicant["fiirumi"] = fiirumi
                    break

            if not found:
                update.message.reply_text(f"Hakijaa ei löydy: {name}")
                raise ValueError(f"Applicant not found: {name}")

            _save_data("data/vaalilakana.json", vaalilakana)

            await update.message.reply_html(
                f'Lisätty Fiirumi:\n{position}: <a href="{fiirumi}">{name}</a>',
            )
    except Exception as e:
        logger.error(e)


async def unassociate_fiirumi(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            division = _find_division_for_position(position)
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                if applicant["name"] == name:
                    applicant["fiirumi"] = ""
                    break
            else:
                # If the loop didn't break
                await update.message.reply_text(
                    "Virheelliset parametrit, hakijaa ei löytynyt roolille"
                )
                return
            _save_data("data/vaalilakana.json", vaalilakana)
            await update.message.reply_text(f"Fiirumi linkki poistettu:\n{name}")
        else:
            # Not admin chat
            pass
    except Exception as e:
        # Unknown error :/
        logger.error(e)


async def add_selected_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            if position not in [position["fi"] for position in positions]:
                await update.message.reply_text(f"Tunnistamaton virka: {position}")
                raise ValueError(f"Unknown position {position}")

            found = False
            division = _find_division_for_position(position)
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                if name == applicant["name"]:
                    found = True
                    applicant["valittu"] = True
                    break

            if not found:
                await update.message.reply_text(f"Hakijaa ei löydy: {name}")
                raise ValueError(f"Applicant not found: {name}")

            _save_data("data/vaalilakana.json", vaalilakana)

            await update.message.reply_text(f"Hakija valittu:\n{position}: {name}")
    except Exception as e:
        logger.error(e)


async def edit_or_add_new_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            if division not in [division["fi"] for division in divisions]:
                await update.message.reply_text(f"Tunnistamaton jaos: {division}")
                raise ValueError(f"Unknown division {division}")

            if role not in [
                role["title"] for role in vaalilakana[division]["roles"].values()
            ]:
                vaalilakana[division]["roles"][role] = {
                    "title": role,
                    "title_en": role_en if role_en else role,
                    "amount": amount,
                    "application_dl": application_dl,
                    "applicants": [],
                }
                positions.append({"fi": role, "en": role_en})
                _save_data("data/vaalilakana.json", vaalilakana)
                await update.message.reply_text(f"Lisätty:\n{division}: {role}")
            else:
                vaalilakana[division]["roles"][role] = {
                    "title": role,
                    "title_en": role_en if role_en else role,
                    "amount": amount,
                    "application_dl": application_dl,
                    "applicants": vaalilakana[division]["roles"][role]["applicants"],
                }
                _save_data("data/vaalilakana.json", vaalilakana)
                await update.message.reply_text(f"Päivitetty:\n{division}: {role}")
    except Exception as e:
        logger.error(e)


async def remove_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            if division not in [division["fi"] for division in divisions]:
                await update.message.reply_text(f"Tunnistamaton jaos: {division}")
                raise ValueError(f"Unknown division {division}")

            if role not in [
                role["title"] for role in vaalilakana[division]["roles"].values()
            ]:
                await update.message.reply_text(f"Tunnistamaton virka: {role}")
                raise ValueError(f"Unknown position {role}")

            del vaalilakana[division]["roles"][role]
            positions.remove({"fi": role, "en": role})
            _save_data("data/vaalilakana.json", vaalilakana)
            await update.message.reply_text(f"Poistettu:\n{division}: {role}")
    except Exception as e:
        logger.error(e)


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                if role not in [position["fi"] for position in positions]:
                    await update.message.reply_text(f"Tunnistamaton virka: {role}")
                    raise ValueError(f"Unknown position {role}")

                division = _find_division_for_position(role)
                for applicant in vaalilakana[division]["roles"][role]["applicants"]:
                    output.write(
                        f"{applicant['name']},{role},{applicant['email']},{applicant['telegram']}\n"
                    )
            else:
                for division in vaalilakana.values():
                    for role in division["roles"].values():
                        for applicant in role["applicants"]:
                            output.write(
                                f"{applicant['name']},{role['title']},{applicant['email']},{applicant['telegram']}\n"
                            )
            output.seek(0)
            await update.message.reply_document(output, filename="applicants.csv")
    except Exception as e:
        logger.error(e)


async def register_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat.id
        if chat_id not in channels:
            channels.append(chat_id)
            _save_data("data/channels.json", channels)
            print(f"New channel added {chat_id}", update.message)
            await update.message.reply_text(
                "Rekisteröity Vaalilakanabotin tiedotuskanavaksi!"
            )
    except Exception as e:
        logger.error(e)


async def show_vaalilakana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_html(
            _vaalilakana_to_string(),
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(e)


async def jauhis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("assets/jauhis.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauhis %s", e)


async def jauh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("assets/jauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauh %s", e)


async def jauho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("assets/jauho.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Jauho %s", e)


async def lauh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("assets/lauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Lauh %s", e)


async def mauh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("assets/mauh.png", "rb") as photo:
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending Mauh %s", e)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_data = context.chat_data
    chat_data.clear()
    await update.message.reply_text("Cancelled current operation.")


async def hae(update: Update, context: CallbackContext) -> int:
    """Apply for a position."""
    keyboard = [
        [
            InlineKeyboardButton("Suomeksi", callback_data="fi"),
            InlineKeyboardButton("In English", callback_data="en"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "In which language would you like to apply?", reply_markup=reply_markup
    )
    return SELECTING_LANGUAGE


def _get_divisions(is_finnish=True):
    return (
        [division["fi"] if is_finnish else division["en"] for division in divisions],
        [division["fi"] for division in divisions],
    )


async def select_language(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    chat_data = context.chat_data
    await query.answer()
    chat_data["is_finnish"] = query.data == "fi" or chat_data["is_finnish"]
    localized_divisions, callback_data = _get_divisions(chat_data["is_finnish"])
    keyboard = InlineKeyboardMarkup(
        _generate_keyboard(localized_divisions, callback_data)
    )
    text = (
        "Minkä jaoksen virkaan haet?"
        if chat_data["is_finnish"]
        else "For which division are you applying?"
    )
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
    )
    return SELECTING_DIVISION


def _get_positions(division, is_finnish=True):
    return (
        [
            role["title"] if is_finnish else role["title_en"]
            for role in vaalilakana[division]["roles"].values()
        ],
        [role["title"] for role in vaalilakana[division]["roles"].values()],
    )


async def select_division(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    chat_data = context.chat_data
    await query.answer()
    chat_data["division"] = query.data
    localized_positions, callback_data = _get_positions(
        query.data, chat_data["is_finnish"]
    )
    keyboard = InlineKeyboardMarkup(
        _generate_keyboard(
            localized_positions,
            callback_data,
            back=("Takaisin" if chat_data["is_finnish"] else "Back"),
        )
    )
    text = (
        "Mihin rooliin haet?"
        if chat_data["is_finnish"]
        else "What position are you applying to?"
    )
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
    )
    return SELECTING_ROLE


async def select_role(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    chat_data = context.chat_data
    await query.answer()

    user_id = update.effective_user.id
    if any(
        applicant["user_id"] == user_id
        for applicant in vaalilakana[chat_data["division"]]["roles"][query.data][
            "applicants"
        ]
    ):
        text = (
            "Olet jo hakenut tähän rooliin!"
            if chat_data["is_finnish"]
            else "You have already applied to this position!"
        )
        await query.edit_message_text(text)
        return ConversationHandler.END

    chat_data["position"] = query.data
    chat_data["loc_position"] = (
        chat_data["position"]
        if chat_data["is_finnish"]
        else vaalilakana[chat_data["division"]]["roles"][query.data]["title_en"]
    )
    chat_data["is_elected"] = chat_data["position"] in ELECTED_OFFICIALS + BOARD
    elected_role_text = "vaaleilla valittavaan " if chat_data["is_elected"] else ""
    elected_role_text_en = "elected " if chat_data["is_elected"] else ""
    text = (
        f"Haet {elected_role_text}rooliin: {chat_data['loc_position']}. Mikä on nimesi?"
        if chat_data["is_finnish"]
        else f"You are applying to the {elected_role_text_en}role: {chat_data['loc_position']}. What is your name?"
    )
    await query.edit_message_text(
        text=text,
    )
    return GIVING_NAME


async def enter_name(update: Update, context: CallbackContext) -> int:
    chat_data = context.chat_data
    name = update.message.text
    chat_data["name"] = name
    text = (
        "Mikä on sähköpostiosoitteesi?"
        if chat_data["is_finnish"]
        else "What is your email address?"
    )
    await update.message.reply_text(text)
    return GIVING_EMAIL


async def enter_email(update: Update, context: CallbackContext) -> int:
    chat_data = context.chat_data
    email = update.message.text
    chat_data["email"] = email
    chat_data["telegram"] = update.message.from_user.username

    elected_text = (
        " (Vaalilakanabot ilmoittaa tästä hakemuksesta kanaville)"
        if chat_data["is_elected"]
        else ""
    )
    elected_text_en = (
        " (Vaalilakanabot will announce this application to the channels)"
        if chat_data["is_elected"]
        else ""
    )

    text = (
        (
            f"Hakemuksesi tiedot: \n"
            f"<b>Haettava rooli</b>: {chat_data['loc_position']}\n"
            f"<b>Nimi</b>: {chat_data['name']}\n"
            f"<b>Sähköposti</b>: {chat_data['email']}\n"
            f"<b>Telegram</b>: {chat_data['telegram']}\n\n"
            f"Haluatko lähettää hakemuksen{elected_text}?"
        )
        if chat_data["is_finnish"]
        else (
            f"Your application details: \n"
            f"<b>Position</b>: {chat_data['loc_position']}\n"
            f"<b>Name</b>: {chat_data['name']}\n"
            f"<b>Email</b>: {chat_data['email']}\n"
            f"<b>Telegram</b>: {chat_data['telegram']}\n\n"
            f"Do you want to send the application {elected_text_en}?"
        )
    )
    text_yes = "Kyllä" if chat_data["is_finnish"] else "Yes"
    text_no = "En" if chat_data["is_finnish"] else "No"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text_yes, callback_data="yes"),
                InlineKeyboardButton(text_no, callback_data="no"),
            ]
        ]
    )

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
    return CONFIRMING_APPLICATION


async def confirm_application(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    chat_data = context.chat_data

    await query.answer()
    try:
        if query.data == "yes":
            name = chat_data["name"]
            position = chat_data["position"]
            email = chat_data["email"]
            telegram = chat_data["telegram"]
            new_applicant = {
                "user_id": update.effective_user.id,
                "name": name,
                "email": email,
                "telegram": telegram,
                "fiirumi": "",
                "valittu": False,
            }

            if position in BOARD + ELECTED_OFFICIALS:
                await _announce_to_channels(
                    f"<b>Uusi nimi vaalilakanassa!</b>\n{position}: <i>{name}</i>",
                    context,
                )

            division = _find_division_for_position(position)
            vaalilakana[division]["roles"][position]["applicants"].append(new_applicant)
            _save_data("data/vaalilakana.json", vaalilakana)

            text = (
                "Hakemuksesi on vastaanotettu. Kiitos!"
                if chat_data["is_finnish"]
                else "Your application has been received. Thank you!"
            )
            await query.edit_message_text(text, reply_markup=None)
        else:
            text = (
                "Hakemuksesi on peruttu."
                if chat_data["is_finnish"]
                else "Your application has been cancelled."
            )
            await query.edit_message_text(text, reply_markup=None)

    except Exception as e:
        # TODO: Return to role selection
        logger.error(e)

    return ConversationHandler.END


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


async def post_init(app: Application):
    jq = app.job_queue
    if jq is None:
        raise ValueError("JobQueue is None")
    jq.run_repeating(parse_fiirumi_posts, interval=60, first=0)
    jq.run_repeating(update_election_sheet, interval=60, first=0)

    app.add_handler(CommandHandler("poista", remove_applicant))
    app.add_handler(CommandHandler("lisaa_fiirumi", add_fiirumi_to_applicant))
    app.add_handler(CommandHandler("poista_fiirumi", unassociate_fiirumi))
    app.add_handler(CommandHandler("valittu", add_selected_tag))
    app.add_handler(CommandHandler("muokkaa_roolia", edit_or_add_new_role))
    app.add_handler(CommandHandler("poista_rooli", remove_role))
    app.add_handler(CommandHandler("vie_tiedot", export_data))
    app.add_handler(CommandHandler("start", register_channel))
    app.add_handler(CommandHandler("lakana", show_vaalilakana))
    app.add_handler(CommandHandler("jauhis", jauhis))
    app.add_handler(CommandHandler("jauh", jauh))
    app.add_handler(CommandHandler("jauho", jauho))
    app.add_handler(CommandHandler("lauh", lauh))
    app.add_handler(CommandHandler("mauh", mauh))

    apply_handler = ConversationHandler(
        entry_points=[CommandHandler("hae", hae, filters.ChatType.PRIVATE)],
        states={
            SELECTING_LANGUAGE: [CallbackQueryHandler(select_language)],
            SELECTING_DIVISION: [CallbackQueryHandler(select_division)],
            SELECTING_ROLE: [
                CallbackQueryHandler(select_language, pattern="back"),
                CallbackQueryHandler(select_role),
            ],
            GIVING_NAME: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), enter_name)
            ],
            GIVING_EMAIL: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), enter_email)
            ],
            CONFIRMING_APPLICATION: [CallbackQueryHandler(confirm_application)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("hae", hae),
        ],
    )

    app.add_handler(apply_handler)

    app.add_error_handler(error)

    logger.info("Post init done.")


def main():
    app = Application.builder().token(TOKEN).concurrent_updates(False).build()
    app.post_init = post_init
    app.run_polling()


if __name__ == "__main__":
    main()
