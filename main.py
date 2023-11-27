import logging
import os
import traceback as tb
import random
import json
import zipfile
import shutil
from queue import Queue
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.ext import Dispatcher, CallbackContext, CommandHandler, CallbackQueryHandler, MessageHandler
from telegram.ext.filters import Filters
from flask import Flask, request
from _env import TELEGRAM_TOKEN, DEBUG, WEBHOOK_URL


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger()


if TELEGRAM_TOKEN is None:
    raise RuntimeError('Telegram token is not set.')


actions = {}

DATA_DIR = 'data'
IMAGE_DIR = os.path.join(DATA_DIR, 'images')
DATA_FILE = os.path.join(DATA_DIR, 'data.json')

print('Init data')
os.makedirs(IMAGE_DIR, exist_ok=True)

if os.path.exists(DATA_FILE):
    with open(DATA_FILE) as f:
        data = json.load(f)
else:
    data = {
        'users': ['Hzom1'],
        'images': []
    }
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def error_wrap(func, exc_types=None):
    if exc_types is None:
        exc_types = (Exception,)

    def wrapper(update: Update, context: CallbackContext):
        try:
            func(update, context)
        except exc_types as e:
            error = tb.format_exc()
            logger.error(error)
            if DEBUG:
                context.bot.send_message(chat_id=update.effective_chat.id, text=error)
            else:
                context.bot.send_message(chat_id=update.effective_chat.id, text=f'Ошибка: {e}')

    return wrapper


def admin_wrap(func):
    def wrapper(update: Update, context: CallbackContext):
        username = update.effective_user.username
        if username in data['users']:
            func(update, context)
        else:
            unknown(update, context)

    return wrapper


_user_menu = InlineKeyboardMarkup([
    [
        InlineKeyboardButton('Вытянуть карту', callback_data='_get_card'),
    ],
])


_admin_menu = InlineKeyboardMarkup([
    [
        InlineKeyboardButton('Вся колода', callback_data='_list_cards'),
        InlineKeyboardButton('Добавить карту', callback_data='_add_card_init'),
        InlineKeyboardButton('Убрать карту', callback_data='_remove_card_init'),
    ],
    [
        InlineKeyboardButton('Админы', callback_data='_list_admins'),
        InlineKeyboardButton('Добавить админа', callback_data='_add_admin_init'),
        InlineKeyboardButton('Удалить админа', callback_data='_delete_admin_init'),
    ],
    [
        InlineKeyboardButton('Скачать данные', callback_data='_save_data'),
        InlineKeyboardButton('Загрузить данные', callback_data='_load_data_init'),
    ],
])


@error_wrap
def start(update: Update, context: CallbackContext):
    print('GOT: start')
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Привет, {update.effective_user.username}',
        reply_markup=_user_menu,
    )


@error_wrap
@admin_wrap
def admin(update: Update, context: CallbackContext):
    print('GOT: admin')
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Привет, {update.effective_user.username}',
        reply_markup=_admin_menu,
    )


@error_wrap
def unknown(update: Update, context: CallbackContext):
    print('GOT: unknown')
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Неизвестная команда',
    )


def _get_card(update: Update, context: CallbackContext):
    if len(data['images']) > 0:
        image = random.choice(data['images'])
        with open(os.path.join(IMAGE_DIR, image['name']), 'rb') as f:
            context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=f,
                caption=f'@{update.effective_user.username}, ваша карта:\n{image["text"]}',
            )
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text='Колода пуста')


@error_wrap
def get_card(update: Update, context: CallbackContext):
    print('GOT: card')
    _get_card(update, context)


@admin_wrap
def _list_cards(update: Update, context: CallbackContext):
    if len(data['images']) > 0:
        message = '\n'.join(f"{i + 1}. {image['name']} {image['text']}"
                            for i, image in enumerate(data['images']))
    else:
        message = 'Колода пуста'
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
def _add_card_init(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Отправьте изображение с подписью в формате jpg, png, gif или webp:',
        disable_web_page_preview=True,
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_add_card_complete'


@admin_wrap
def _add_card_complete(update: Update, context: CallbackContext):
    try:
        attachment = update.effective_message.effective_attachment[-1]
    except TypeError:
        message = 'Файл отсутствует или имеет неверный формат'
    else:
        file = attachment.get_file()
        filename = str(file.download())
        os.rename(filename, os.path.join(IMAGE_DIR, filename))
        caption = update.effective_message.caption
        if caption is None:
            caption = ''
        data['images'].append({'name': filename, 'text': caption})
        save_data()
        message = 'Карта добавлена'

    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
def _remove_card_init(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите порядковый номер карты в списке:',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_remove_card_complete'


@admin_wrap
def _remove_card_complete(update: Update, context: CallbackContext):
    try:
        idx = int(update.message.text)
        card = data['images'].pop(idx - 1)
    except ValueError:
        message = 'Неправильный номер'
    except IndexError:
        message = 'Номера нет в списке'
    else:
        os.remove(os.path.join(IMAGE_DIR, card['name']))
        save_data()
        message = f'Карта удалена: {card["name"]}, {card["text"]}'
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
def _list_admins(update: Update, context: CallbackContext):
    if len(data['users']) > 0:
        message = '\n'.join(f"{i + 1}. {user}" for i, user in enumerate(data['users']))
    else:
        message = 'Админов нет'
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
def _add_admin_init(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите имя пользователя без "@", например:\nHzom1',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_add_admin_complete'


@admin_wrap
def _add_admin_complete(update: Update, context: CallbackContext):
    user = update.message.text
    if user in data['users']:
        message = f'{user} уже админ'
    else:
        data['users'].append(user)
        save_data()
        message = f'Новый админ: {user}'
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
def _delete_admin_init(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите порядковый номер админа в списке:',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_delete_admin_complete'


@admin_wrap
def _delete_admin_complete(update: Update, context: CallbackContext):
    try:
        idx = int(update.message.text)
        user = data['users'].pop(idx - 1)
    except ValueError:
        message = 'Неправильный номер'
    except IndexError:
        message = 'Номера нет в списке'
    else:
        if len(data['users']) < 1:
            data['users'].append(update.effective_user.username)
        save_data()
        message = f'Админ удалён: {user}'
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
def _save_data(update: Update, context: CallbackContext):
    filename = 'card_bot_data.zip'

    with zipfile.ZipFile(filename, 'w') as f:
        for image in data['images']:
            f.write(os.path.join(IMAGE_DIR, image['name']), os.path.join('images', image['name']))
        f.write(DATA_FILE, 'data.json')

    try:
        with open(filename, 'rb') as f:
            context.bot.send_document(chat_id=update.effective_chat.id, document=f)
    finally:
        os.remove(filename)


@admin_wrap
def _load_data_init(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Отправьте zip архив c данными и изображениями:',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_load_data_complete'


@admin_wrap
def _load_data_complete(update: Update, context: CallbackContext):
    global data

    if os.path.exists('old_data'):
        message = 'Архив уже загружается'
    else:
        attachment = update.effective_message.effective_attachment
        file = attachment.get_file()
        path = file.download()

        os.rename(DATA_DIR, 'old_data')

        try:
            with zipfile.ZipFile(path, 'r') as f:
                f.extractall(DATA_DIR)

            with open(DATA_FILE) as f:
                data = json.load(f)

            if update.effective_user.username not in data['users']:
                data['users'].append(update.effective_user.username)
                save_data()
        except Exception:
            shutil.rmtree(DATA_DIR, ignore_errors=True)
            os.rename('old_data', DATA_DIR)

            with open(DATA_FILE) as f:
                data = json.load(f)

            raise
        else:
            shutil.rmtree('old_data', ignore_errors=True)
            message = 'Данные загружены'
        finally:
            os.remove(path)

    context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@error_wrap
def action(update: Update, context: CallbackContext):
    print('GOT: action')
    action_name = actions.pop(f'{update.effective_user.username}_{update.effective_chat.id}', None)
    if action_name is not None:
        handler = globals().get(action_name)
        if handler is not None:
            handler(update, context)


@error_wrap
def menu(update: Update, context: CallbackContext):
    print('GOT: menu')
    query = update.callback_query
    query.answer()

    handler = globals().get(query.data)
    if handler is not None:
        handler(update, context)


print('Init bot')
bot = Bot(TELEGRAM_TOKEN)
bot.set_webhook(WEBHOOK_URL)
update_queue = Queue()
dp = Dispatcher(bot=bot, update_queue=update_queue)

start_handler = CommandHandler('start', start, filters=Filters.chat_type.private)
dp.add_handler(start_handler)

admin_handler = CommandHandler('admin', admin, filters=Filters.chat_type.private)
dp.add_handler(admin_handler)

card_handler = CommandHandler('card', get_card)
dp.add_handler(card_handler)

menu_handler = CallbackQueryHandler(menu)
dp.add_handler(menu_handler)

action_handler = MessageHandler(~Filters.command, action)
dp.add_handler(action_handler)

unknown_handler = MessageHandler(Filters.command & Filters.chat_type.private, unknown)
dp.add_handler(unknown_handler)


flask_app = Flask(__name__)


@flask_app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.json:
        dp.process_update(Update.de_json(request.json, bot))
    return ''
