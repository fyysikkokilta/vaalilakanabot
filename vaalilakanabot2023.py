import json
import os
import time
import random
from glob import glob

import logging
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, MessageHandler, CommandHandler, \
    Filters, ConversationHandler, CallbackContext, CallbackQueryHandler

TOKEN = os.environ['VAALILAKANABOT_TOKEN']
ADMIN_CHAT_ID = os.environ['ADMIN_CHAT_ID']

BASE_URL = 'https://fiirumi.fyysikkokilta.fi'

# TODO: update these to correspond current year discussion board
TOPIC_LIST_URL = f'{BASE_URL}/c/vaalipeli-2023/esittelyt/l/latest.json'
QUESTION_LIST_URL = f'{BASE_URL}/c/vaalipeli-2023/kysymykset/l/latest.json'

BOARD = ['Puheenjohtaja', 'Varapuheenjohtaja', 'Rahastonhoitaja', 'Viestintävastaava',
         'IE', 'Hupimestari', 'Yrityssuhdevastaava', 'Kv-vastaava', 'Opintovastaava',
         'Fuksikapteeni']

OFFICIALS = ['ISOvastaava', 'Excumestari',
             'Lukkarimestari', 'Kvantin päätoimittaja']

SELECTING_POSITION_CLASS, SELECTING_POSITION, TYPING_NAME, CONFIRMING = range(4)

channels = []
vaalilakana = {}
last_applicant = None
fiirumi_posts = []
question_posts = []

logger = logging.getLogger('vaalilakanabot')
logger.setLevel(logging.INFO)

log_path = os.path.join('logs', 'vaalilakanabot.log')
fh = logging.FileHandler(log_path)
fh.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

with open('data/vaalilakana.json', 'r') as f:
    data = f.read()
    vaalilakana = json.loads(data)

logger.info('Loaded vaalilakana: %s', vaalilakana)

with open('data/channels.json', 'r') as f:
    data = f.read()
    channels = json.loads(data)

logger.info('Loaded channels: %s', channels)

with open('data/fiirumi_posts.json', 'r') as f:
    data = f.read()
    fiirumi_posts = json.loads(data)

logger.info('Loaded fiirumi posts: %s', fiirumi_posts)

with open('data/question_posts.json', 'r') as f:
    data = f.read()
    question_posts = json.loads(data)

logger.info('Loaded question posts: %s', fiirumi_posts)

updater = Updater(TOKEN, use_context=True)


def _save_data(filename, content):
    with open(filename, 'w') as fp:
        fp.write(json.dumps(content))


def _vaalilakana_to_string(lakana):
    output = ''
    output += '<b>---------------Raati---------------</b>\n'
    # Hardcoded to maintain order instead using dict keys
    for position in BOARD:
        output += f'<b>{position}:</b>\n'
        for applicant in lakana[position]:
            link = applicant['fiirumi']
            selected = applicant['valittu']
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

        output += '\n'
    output += '<b>----------Toimihenkilöt----------</b>\n'
    for position in OFFICIALS:
        output += f'<b>{position}:</b>\n'
        for applicant in lakana[position]:
            link = applicant['fiirumi']
            selected = applicant['valittu']
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

        output += '\n'
    return output


def parse_fiirumi_posts(context=updater.bot):
    try:
        page_fiirumi = requests.get(TOPIC_LIST_URL)
        logger.debug(page_fiirumi)
        page_question = requests.get(QUESTION_LIST_URL)
        topic_list_raw = page_fiirumi.json()
        logger.debug(str(topic_list_raw))
        question_list_raw = page_question.json()
        topic_list = topic_list_raw['topic_list']['topics']
        question_list = question_list_raw['topic_list']['topics']

        logger.debug(topic_list)
    except KeyError as e:
        logger.error("The topic and question lists cannot be found. Check URLs. Got error %s", e)
        return
    except Exception as e:
        logger.error(e)
        return

    for topic in topic_list:
        t_id = topic['id']
        title = topic['title']
        slug = topic['slug']
        if str(t_id) not in fiirumi_posts:
            new_post = {
                'id': t_id,
                'title': title,
                'slug': slug,
            }
            fiirumi_posts[str(t_id)] = new_post
            _save_data('data/fiirumi_posts.json', fiirumi_posts)
            _announce_to_channels(
                f'<b>Uusi postaus Vaalipeli-palstalla!</b>\n{title}\n{BASE_URL}/t/{slug}/{t_id}'
            )

    for question in question_list:
        t_id = question['id']
        title = question['title']
        slug = question['slug']
        if str(t_id) not in question_posts:
            new_question = {
                'id': t_id,
                'title': title,
                'slug': slug,
            }
            question_posts[str(t_id)] = new_question
            _save_data('data/question_posts.json', question_posts)
            _announce_to_channels(
                f'<b>Uusi kysymys Fiirumilla!</b>\n{title}\n{BASE_URL}/t/{slug}/{t_id}'
            )


def _announce_to_channels(message):
    for cid in channels:
        try:
            updater.bot.send_message(cid, message, parse_mode='HTML')
            time.sleep(0.5)
        except Exception as e:
            logger.error(e)
            continue


def remove_applicant(update, context):
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace('/poista', '').strip()
            params = text.split(',')

            try:
                position = params[0].strip()
                name = params[1].strip()
            except Exception as e:
                updater.bot.send_message(
                    chat_id,
                    'Virheelliset parametrit - /poista <virka>, <nimi>'
                )
                raise Exception('Invalid parameters') from e

            if position not in vaalilakana:
                updater.bot.send_message(
                    chat_id,
                    f'Tunnistamaton virka: {position}',
                    parse_mode='HTML'
                )
                raise Exception(f'Unknown position {position}')

            found = None
            for applicant in vaalilakana[position]:
                if name == applicant['name']:
                    found = applicant
                    break

            if not found:
                updater.bot.send_message(
                    chat_id,
                    f'Hakijaa ei löydy {name}',
                    parse_mode='HTML'
                )
                raise Exception(f'Applicant not found: {name}')

            vaalilakana[position].remove(found)
            _save_data('data/vaalilakana.json', vaalilakana)
            global last_applicant
            last_applicant = None

            updater.bot.send_message(
                chat_id,
                'Poistettu:\n{position}: {name}'.format(
                    **found
                ),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(e)


def add_fiirumi_to_applicant(update, context):
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace('/lisaa_fiirumi', '').strip()
            params = text.split(',')

            try:
                position = params[0].strip()
                name = params[1].strip()
                thread_id = params[2].strip()
            except Exception as e:
                updater.bot.send_message(
                    chat_id,
                    'Virheelliset parametrit - /lisaa_fiirumi <virka>, <nimi>, <thread id>'
                )
                raise Exception('Invalid parameters') from e

            if position not in vaalilakana:
                updater.bot.send_message(
                    chat_id,
                    f'Tunnistamaton virka: {position}',
                    parse_mode='HTML'
                )
                raise Exception(f'Unknown position {position}')

            if thread_id not in fiirumi_posts:
                updater.bot.send_message(
                    chat_id,
                    f'Fiirumi-postausta ei löytynyt annetulla id:llä: {thread_id}',
                    parse_mode='HTML'
                )
                raise Exception(f'Unknown thread {thread_id}')

            found = None
            for applicant in vaalilakana[position]:
                if name == applicant['name']:
                    found = applicant
                    fiirumi = f'{BASE_URL}/t/{fiirumi_posts[thread_id]["slug"]}/{fiirumi_posts[thread_id]["id"]}'
                    applicant['fiirumi'] = fiirumi
                    break

            if not found:
                updater.bot.send_message(
                    chat_id,
                    f'Hakijaa ei löydy {name}',
                    parse_mode='HTML'
                )
                raise Exception(f'Applicant not found: {name}')

            _save_data('data/vaalilakana.json', vaalilakana)
            global last_applicant
            last_applicant = None

            updater.bot.send_message(
                chat_id,
                'Lisätty Fiirumi:\n{position}: <a href="{fiirumi}">{name}</a>'.format(
                    fiirumi,
                    **found
                ),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(e)


def add_applicant(update: Update, context: CallbackContext) -> None:
    """Add an applicant. This command is for admin use."""
    keyboard = [[
        InlineKeyboardButton("Raatiin", callback_data='board'),
        InlineKeyboardButton("Toimihenkilöksi", callback_data='official'),
    ]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    chat_id = update.message.chat.id
    if str(chat_id) == str(ADMIN_CHAT_ID):
        update.message.reply_text('Mihin rooliin henkilö lisätään?', reply_markup=reply_markup)
        return SELECTING_POSITION_CLASS
    else:
        update.message.reply_text('Et oo admin :(((')
        return None


def generate_positions(position_class):
    keyboard = []
    for position in position_class:
        keyboard.append(
            [InlineKeyboardButton(position, callback_data=position)]
        )
    return keyboard


def select_position_class(update: Update, context: CallbackContext) -> int:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    query.answer()
    chat_data = context.chat_data
    logger.debug(str(chat_data))

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    if query.data == '1':
        logger.debug('Raati')
        keyboard = InlineKeyboardMarkup(generate_positions(BOARD))
        query.edit_message_reply_markup(keyboard)
        return SELECTING_POSITION
    elif query.data == '2':
        logger.debug('Toimihenkilö')
        keyboard = InlineKeyboardMarkup(generate_positions(OFFICIALS))
        query.edit_message_reply_markup(keyboard)
        return SELECTING_POSITION
    else:
        return SELECTING_POSITION_CLASS


def select_board_position(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup(generate_positions(BOARD))
    query.edit_message_reply_markup(keyboard)
    return SELECTING_POSITION


def select_official_position(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup(generate_positions(OFFICIALS))
    query.edit_message_reply_markup(keyboard)
    return SELECTING_POSITION


def register_position(update: Update, context: CallbackContext) -> int:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    chat_data = context.chat_data

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()
    query.edit_message_text(text=f"Hakija rooliin: {query.data}\nKirjoita hakijan nimi vastauksena tähän viestiin")
    chat_data['new_applicant_position'] = query.data
    return TYPING_NAME


def enter_applicant_name(update: Update, context: CallbackContext) -> int:
    """Stores the info about the user and ends the conversation."""
    chat_data = context.chat_data
    logger.debug(chat_data)
    name = update.message.text
    logger.debug(name)
    try:
        chat_id = update.message.chat.id
        position = chat_data['new_applicant_position']
        chat_data['new_applicant_name'] = name

        new_applicant = {'name': name, 'position': position, 'fiirumi': '', 'valittu': False}

        vaalilakana[position].append(new_applicant)
        _save_data('data/vaalilakana.json', vaalilakana)
        global last_applicant
        last_applicant = new_applicant

        updater.bot.send_message(
            chat_id,
            'Lisätty:\n{position}: {name}.\n\nLähetä tiedote komennolla /tiedota'.format(
                **new_applicant
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        # TODO: Return to role selection
        logger.error(e)
    return ConversationHandler.END

def unassociate_fiirumi(update, context):
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            # Converts /poista_fiirumi Puheenjohtaja, Fysisti kiltalainen
            # to ["Puheenjohtaja", "Fysisti kiltalainen"]
            params = [
                arg.strip()
                for arg in update.message.text.replace('/poista_fiirumi','').strip().split(',')
            ]
            # Try find role
            try:
                role, applicant = params
            except Exception as e:
                updater.bot.send_message(chat_id, 'Virheelliset parametrit - /poista_fiirumi <virka>, <nimi>')
                return

            if role not in vaalilakana:
                updater.bot.send_message(chat_id, 'Virheelliset parametrit, roolia ei löytynyt')
                return

            # Try finding the dict with matching applicant name from vaalilakana
            for app_info in vaalilakana[role]:
                if app_info['name'] == applicant:
                    app_info['fiirumi'] = ""
                    break
            else:
                # If the loop didn't break
                updater.bot.send_message(chat_id, 'Virheelliset parametrit, hakijaa ei löytynyt roolille')
                return
            _save_data('data/vaalilakana.json', vaalilakana)
            updater.bot.send_message(
                chat_id,
                'Fiirumi linkki poistettu:\n{name}'.format(
                    name=applicant
                ),
                parse_mode='HTML'
            )
        else:
            # Not admin chat
            pass
    except Exception as e:
        # Unknown error :/
        logger.error(e)
            

def add_selected_tag(update, context):
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            text = update.message.text.replace('/valittu', '').strip()
            params = text.split(',')

            try:
                position = params[0].strip()
                name = params[1].strip()
            except Exception as e:
                updater.bot.send_message(
                    chat_id,
                    'Virheelliset parametrit - /valittu <virka>, <nimi>'
                )
                raise Exception from e

            if position not in vaalilakana:
                updater.bot.send_message(
                    chat_id,
                    f'Tunnistamaton virka: {position}',
                    parse_mode='HTML'
                )
                raise Exception(f'Unknown position {position}')

            found = None
            for applicant in vaalilakana[position]:
                if name == applicant['name']:
                    found = applicant
                    applicant['valittu'] = True
                    break

            if not found:
                updater.bot.send_message(
                    chat_id,
                    f'Hakijaa ei löydy {name}',
                    parse_mode='HTML'
                )
                raise Exception(f'Applicant not found: {name}')

            _save_data('data/vaalilakana.json', vaalilakana)
            global last_applicant
            last_applicant = None

            updater.bot.send_message(
                chat_id,
                'Hakija valittu:\n{position}: {name}'.format(
                    **found
                ),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(e)


def show_vaalilakana(update, context):
    try:
        chat_id = update.message.chat.id
        updater.bot.send_message(
            chat_id,
            _vaalilakana_to_string(vaalilakana),
            parse_mode='HTML', disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(e)


def register_channel(update, context):
    try:
        chat_id = update.message.chat.id
        if chat_id not in channels:
            channels.append(chat_id)
            _save_data('data/channels.json', channels)
            print(f'New channel added {chat_id}', update.message)
            updater.bot.send_message(
                chat_id,
                'Rekisteröity Vaalilakanabotin tiedotuskanavaksi!'
            )
    except Exception as e:
        logger.error(e)


def announce_new_applicant(update, context):
    try:
        chat_id = update.message.chat.id
        if str(chat_id) == str(ADMIN_CHAT_ID):
            global last_applicant
            if last_applicant:
                _announce_to_channels(
                    '<b>Uusi nimi vaalilakanassa!</b>\n{position}: <i>{name}</i>'.format(
                        **last_applicant
                    )
                )
            last_applicant = None
    except Exception as e:
        logger.error(e)


def jauhis(update, context):
    try:
        chat_id = update.message.chat.id
        with open('assets/jauhis.png', 'rb') as photo:
            updater.bot.send_sticker(chat_id, photo)
    except Exception as e:
        logger.warning("Error in sending Jauhis %s", e)


def jauh(update, context):
    try:
        chat_id = update.message.chat.id
        with open('assets/jauh.png', 'rb') as photo:
            updater.bot.send_sticker(chat_id, photo)
    except Exception as e:
        logger.warning("Error in sending Jauh %s", e)
        
        
def lauh(update, context):
    try:
        chat_id = update.message.chat.id
        with open('assets/lauh.png', 'rb') as photo:
            updater.bot.send_sticker(chat_id, photo)
    except Exception as e:
        logger.warning("Error in sending Lauh %s", e)


def mauh(update, context):
    try:
        chat_id = update.message.chat.id
        with open('assets/mauh.png', 'rb') as photo:
            updater.bot.send_sticker(chat_id, photo)
    except Exception as e:
        logger.warning("Error in sending Mauh %s", e)        


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def cancel(update, context):
    chat_data = context.chat_data
    chat_data.clear()


        

def main():
    jq = updater.job_queue
    jq.run_repeating(parse_fiirumi_posts, interval=60, first=0, context=updater.bot)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler('valittu', add_selected_tag))
    dp.add_handler(CommandHandler('lisaa_fiirumi', add_fiirumi_to_applicant))
    dp.add_handler(CommandHandler('poista_fiirumi', unassociate_fiirumi))
    dp.add_handler(CommandHandler('poista', remove_applicant))
    dp.add_handler(CommandHandler('lakana', show_vaalilakana))
    dp.add_handler(CommandHandler('tiedota', announce_new_applicant))
    dp.add_handler(CommandHandler('start', register_channel))
    dp.add_handler(CommandHandler('jauhis', jauhis))
    dp.add_handler(CommandHandler('jauh', jauh))
    dp.add_handler(CommandHandler('lauh', lauh))
    dp.add_handler(CommandHandler('mauh', mauh))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('lisaa', add_applicant)],
        states={
            SELECTING_POSITION_CLASS: [
                CallbackQueryHandler(select_board_position, pattern='^board$'),
                CallbackQueryHandler(select_official_position, pattern='^official$')
            ],
            SELECTING_POSITION: [
                CallbackQueryHandler(register_position)
            ],
            TYPING_NAME: [MessageHandler(Filters.text & (~Filters.command), enter_applicant_name)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('lisaa', add_applicant)],
    )

    dp.add_handler(conv_handler)

    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
