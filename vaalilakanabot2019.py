import os
import re
import time
import json
import requests

from telegram.ext import Updater, MessageHandler, CommandHandler, Filters
from lxml import html, etree

TOKEN = os.environ['VAALILAKANABOT_TOKEN']
ADMIN_CHAT_ID = # TODO fill chat id here

BASE_URL = 'https://fiirumi.fyysikkokilta.fi'
TOPIC_LIST_URL = '{}/c/5.json'.format(BASE_URL) #TODO: update this to correspond current year discussion board
QUESTION_LIST_URL = '{}/c/6.json'.format(BASE_URL) #TODO: update this to correspond current year discussion board

channels = []
vaalilakana = {}
last_applicant = None
fiirumi_posts = []
question_posts = []

with open('vaalilakana.json', 'r') as f:
    data = f.read()
    vaalilakana = json.loads(data)

print('Loaded vaalilakana: {}'.format(vaalilakana))

with open('channels.json', 'r') as f:
    data = f.read()
    channels = json.loads(data)

print('Loaded channels: {}'.format(channels))

with open('fiirumi_posts.json', 'r') as f:
    data = f.read()
    fiirumi_posts = json.loads(data)

print('Loaded fiirumi posts: {}'.format(fiirumi_posts))

with open('question_posts.json', 'r') as f:
    data = f.read()
    question_posts = json.loads(data)

print('Loaded question posts: {}'.format(fiirumi_posts))

updater = Updater(TOKEN, use_context=True)


def _save_data(filename, data):
    with open(filename, 'w') as f:
        f.write(json.dumps(data))


def _vaalilakana_to_string(vaalilakana):
    output = ''
    # Hardcoded to maintain order instead using dict keys
    for position in ['Puheenjohtaja', 'Varapuheenjohtaja', 'Rahastonhoitaja', 'Viestintävastaava',
            'IE', 'Hupimestari', 'Yrityssuhdevastaava', 'Kv-vastaava', 'Opintovastaava', 'Fuksikapteeni']:
        output += '<b>{position}:</b>\n'.format(position=position)
        for applicant in vaalilakana[position]:
            link = applicant['fiirumi']
            selected = applicant['valittu']
            if selected == True:
                if link:
                    output += '- <a href="{link}">{name}</a> (valittu)\n'.format(
                        name=applicant['name'],
                        link=link
                    )
                else:
                    output += '- {name} (valittu)\n'.format(name=applicant['name'])
            else:
                if link:
                    output += '- <a href="{link}">{name}</a>\n'.format(
                        name=applicant['name'],
                        link=link
                    )
                else:
                    output += '- {name}\n'.format(name=applicant['name'])

        output += '\n'
    return output


def _parse_fiirumi_posts():
    try:
        page_fiirumi = requests.get(TOPIC_LIST_URL)
        page_question = requests.get(QUESTION_LIST_URL)
        topic_list_raw = page_fiirumi.json()
        question_list_raw = page_question.json()
        topic_list= topic_list_raw['topic_list']['topics']
        question_list = question_list_raw['topic_list']['topics']
    except Exception as e:
        print('[ERROR]', e)
        return
		
    for topic in topic_list:
        id = topic['id']
        title = topic['title']
        slug = topic['slug']
        if str(id) not in fiirumi_posts:
            new_post = {
                'id': id,
                'title': title,
                'slug': slug,
            }
            fiirumi_posts[str(id)] = new_post
            _save_data('fiirumi_posts.json', fiirumi_posts)
            _announce_to_channels(
                '<b>Uusi postaus Vaalipeli-palstalla!</b>\n{title}\n{base}/t/{slug}/{id}'.format(
                    title=title,
                    base=BASE_URL,
                    slug=slug,
			 	id=id
                )
            )
			
    for question in question_list:
        id = question['id']
        title = question['title']
        slug = question['slug']
        if str(id) not in question_posts:
            new_question = {
                'id': id,
                'title': title,
                'slug': slug,
            }
            question_posts[str(id)] = new_question 
            _save_data('question_posts.json', question_posts)
            _announce_to_channels(
                '<b>Uusi kysymys Fiirumilla!</b>\n{title}\n{base}/t/{slug}/{id}'.format(
                    title=title,
                    base=BASE_URL,
                    slug=slug,
			 	id=id
                )
            )


def _announce_to_channels(message):
    for cid in channels:
        try:
            updater.bot.send_message(cid, message, parse_mode='HTML')
            time.sleep(0.5)
        except Exception as e:
            print('[ERROR]', e)
            continue


def remove_applicant(update, context):
    try:
        chat_id = update.message.chat.id
        if chat_id == ADMIN_CHAT_ID:
            text = update.message.text.replace('/poista', '').strip()
            params = text.split(',')
            
            try:
                position = params[0].strip()
                name = params[1].strip()
            except:
                updater.bot.send_message(
                    chat_id,
                    'Virheelliset parametrit - /poista <virka>, <nimi>'
                )
                raise Exception('Invalid parameters')

            if position not in vaalilakana:
                updater.bot.send_message(
                    chat_id,
                    'Tunnistamaton virka: {}'.format(position),
                    parse_mode='HTML'
                )
                raise Exception('Unknown position {}'.format(position))
            
            found = None
            for applicant in vaalilakana[position]:
                if name == applicant['name']:
                    found = applicant
                    break

            if not found:
                updater.bot.send_message(
                    chat_id,
                    'Hakijaa ei löydy {}'.format(name),
                    parse_mode='HTML'
                )
                raise Exception('Applicant not found: {}'.format(name))

            vaalilakana[position].remove(found)
            _save_data('vaalilakana.json', vaalilakana)
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
        print('[ERROR]', e)


def add_fiirumi_to_applicant(update, context):
    try:
        chat_id = update.message.chat.id
        if chat_id == ADMIN_CHAT_ID:
            text = update.message.text.replace('/lisaa_fiirumi', '').strip()
            params = text.split(',')
            
            try:
                position = params[0].strip()
                name = params[1].strip()
                thread_id = params[2].strip()
            except:
                updater.bot.send_message(
                    chat_id,
                    'Virheelliset parametrit - /lisaa_fiirumi <virka>, <nimi>, <thread id>'
                )
                raise Exception('Invalid parameters')

            if position not in vaalilakana:
                updater.bot.send_message(
                    chat_id,
                    'Tunnistamaton virka: {}'.format(position),
                    parse_mode='HTML'
                )
                raise Exception('Unknown position {}'.format(position))
				
            if thread_id not in fiirumi_posts:
                updater.bot.send_message(
                    chat_id,
                    'Fiirumi-postausta ei löytynyt annetulla id:llä: {}'.format(thread_id),
                    parse_mode='HTML'
                )
                raise Exception('Unknown thread {}'.format(thread_id))
            
            found = None
            for applicant in vaalilakana[position]:
                if name == applicant['name']:
                    found = applicant
                    fiirumi = '{base}/t/{slug}/{thread_id}'.format(
                        base = BASE_URL,
                        slug = fiirumi_posts[thread_id]['slug'],
                        thread_id = fiirumi_posts[thread_id]['id'])
                    applicant['fiirumi'] = fiirumi
                    break

            if not found:
                updater.bot.send_message(
                    chat_id,
                    'Hakijaa ei löydy {}'.format(name),
                    parse_mode='HTML'
                )
                raise Exception('Apllicant not found: {}'.format(name))

            _save_data('vaalilakana.json', vaalilakana)
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
        print('[ERROR]', e)


def add_applicant(update, context):
    try:
        chat_id = update.message.chat.id
        print(chat_id)
        if chat_id == ADMIN_CHAT_ID:
            text = update.message.text.replace('/lisaa', '').strip()
            params = text.split(',')
            
            try:
                position = params[0].strip()
                name = params[1].strip()
                fiirumi = ''
                if len(params) > 2:
                    thread_id = params[2].strip()
                    fiirumi = '{base}/t/{slug}/{thread_id}'.format(
                        base = BASE_URL,
                        slug = fiirumi_posts[thread_id]['slug'],
                        thread_id = fiirumi_posts[thread_id]['id'])
            except:
                updater.bot.send_message(
                    chat_id,
                    'Virheelliset parametrit - /lisaa <virka>, <nimi>, thread ID'
                )
                raise Exception('Invalid parameters')
            
            new_applicant = {
                'name': name,
                'position': position,
                'fiirumi': fiirumi,
				'valittu': False
            }

            if position not in vaalilakana:
                updater.bot.send_message(
                    chat_id,
                    'Tunnistamaton virka: {}'.format(position),
                    parse_mode='HTML'
                )
                raise Exception('Unknown position {}'.format(position))

            vaalilakana[position].append(new_applicant)
            _save_data('vaalilakana.json', vaalilakana)
            global last_applicant
            last_applicant = new_applicant

            updater.bot.send_message(
                chat_id,
                'Lisätty:\n{position}: {name} ({fiirumi}).\n\nLähetä tiedote komennolla /tiedota'.format(
                    **new_applicant
                ),
                parse_mode='HTML'
            )

    except Exception as e:
        print('[ERROR]', e)
		
def add_selected_tag(update, context):
    try:
        chat_id = update.message.chat.id
        if chat_id == ADMIN_CHAT_ID:
            text = update.message.text.replace('/valittu', '').strip()
            params = text.split(',')
            
            try:
                position = params[0].strip()
                name = params[1].strip()
            except:
                updater.bot.send_message(
                    chat_id,
                    'Virheelliset parametrit - /valittu <virka>, <nimi>'
                )
                raise Exception('Invalid parameters')

            if position not in vaalilakana:
                updater.bot.send_message(
                    chat_id,
                    'Tunnistamaton virka: {}'.format(position),
                    parse_mode='HTML'
                )
                raise Exception('Unknown position {}'.format(position))
            
            found = None
            for applicant in vaalilakana[position]:
                if name == applicant['name']:
                    found = applicant
                    applicant['valittu'] = True
                    break

            if not found:
                updater.bot.send_message(
                    chat_id,
                    'Hakijaa ei löydy {}'.format(name),
                    parse_mode='HTML'
                )
                raise Exception('Apllicant not found: {}'.format(name))

            _save_data('vaalilakana.json', vaalilakana)
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
        print('[ERROR]', e)


def show_vaalilakana(update, context):
    try:
        chat_id = update.message.chat.id
        updater.bot.send_message(
            chat_id,
            _vaalilakana_to_string(vaalilakana),
            parse_mode='HTML', disable_web_page_preview = True
        )
    except Exception as e:
        print('[ERROR]', e)


def register_channel(update, context):
    try:
        chat_id = update.message.chat.id
        if chat_id not in channels:
            channels.append(chat_id)
            _save_data('channels.json', channels)
            print('New channel added {}'.format(chat_id), update.message)
            updater.bot.send_message(
                chat_id,
                'Rekisteröity Vaalilakanabotin tiedotuskanavaksi!'
            )
    except Exception as e:
        print('[ERROR]', e)


def announce_new_applicant(update, context):
    try:
        chat_id = update.message.chat.id
        if chat_id == ADMIN_CHAT_ID:
            global last_applicant
            if last_applicant:
                _announce_to_channels(
                    '<b>Uusi nimi vaalilakanassa!</b>\n{position}: <i>{name}</i>'.format(
                        **last_applicant
                    )
                )
            last_applicant = None
    except Exception as e:
        print('[ERROR]', e)


def jauhis(update, context):
    try:
        chat_id = update.message.chat.id
        with open('jauhis.png', 'rb') as jauhis:
            updater.bot.send_sticker(chat_id, jauhis)
    except Exception as e:
        print('[ERROR]', e)


updater.dispatcher.add_handler(CommandHandler('lisaa', add_applicant))
updater.dispatcher.add_handler(CommandHandler('valittu', add_selected_tag))
updater.dispatcher.add_handler(CommandHandler('lisaa_fiirumi', add_fiirumi_to_applicant))
updater.dispatcher.add_handler(CommandHandler('poista', remove_applicant))
updater.dispatcher.add_handler(CommandHandler('lakana', show_vaalilakana))
updater.dispatcher.add_handler(CommandHandler('tiedota', announce_new_applicant))
updater.dispatcher.add_handler(CommandHandler('start', register_channel))
updater.dispatcher.add_handler(CommandHandler('jauhis', jauhis))

updater.start_polling()
# updater.idle()

while True:
    _parse_fiirumi_posts()
    time.sleep(60)
