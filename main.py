import logging
import os
import traceback as tb
import random
import json
import zipfile
import shutil
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger()

DEBUG = os.getenv('DEBUG', '0').lower() in ('true', 'yes', 'on', '1')
TOKEN = os.getenv('TELEGRAM_TOKEN')
MODE = os.getenv('TELEGRAM_MODE')

if TOKEN is None:
    raise RuntimeError('Telegram token is not set.')


actions = {}

DATA_DIR = 'data'
IMAGE_DIR = os.path.join(DATA_DIR, 'images')
DATA_FILE = os.path.join(DATA_DIR, 'data.json')

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

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await func(update, context)
        except exc_types as e:
            error = tb.format_exc()
            logger.error(error)
            if DEBUG:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=error)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Ошибка: {e}')

    return wrapper


def admin_wrap(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.effective_user.username
        if username in data['users']:
            await func(update, context)
        else:
            await unknown(update, context)

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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Привет, {update.effective_user.username}',
        reply_markup=_user_menu,
    )


@error_wrap
@admin_wrap
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Привет, {update.effective_user.username}',
        reply_markup=_admin_menu,
    )


@error_wrap
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Неизвестная команда',
    )


@admin_wrap
async def _get_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(data['images']) > 0:
        image = random.choice(data['images'])
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=os.path.join(IMAGE_DIR, image['name']),
            caption=image['text'],
        )
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Колода пуста')


@admin_wrap
async def _list_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(data['images']) > 0:
        message = '\n'.join(f"{i + 1}. {image['name']} {image['text']}"
                            for i, image in enumerate(data['images']))
    else:
        message = 'Колода пуста'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
async def _add_card_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Отправьте изображение с подписью в формате jpg, png, gif или webp:',
        disable_web_page_preview=True,
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_add_card_complete'


@admin_wrap
async def _add_card_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        attachment = update.effective_message.effective_attachment[-1]
    except TypeError:
        message = 'Файл отсутствует или имеет неверный формат'
    else:
        file = await attachment.get_file()
        filename = str(await file.download_to_drive())
        os.rename(filename, os.path.join(IMAGE_DIR, filename))
        caption = update.effective_message.caption
        if caption is None:
            caption = ''
        data['images'].append({'name': filename, 'text': caption})
        save_data()
        message = 'Карта добавлена'

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
async def _remove_card_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите порядковый номер карты в списке:',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_remove_card_complete'


@admin_wrap
async def _remove_card_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
async def _list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(data['users']) > 0:
        message = '\n'.join(f"{i + 1}. {user}" for i, user in enumerate(data['users']))
    else:
        message = 'Админов нет'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
async def _add_admin_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите имя пользователя без "@", например:\nHzom1',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_add_admin_complete'


@admin_wrap
async def _add_admin_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.text
    if user in data['users']:
        message = f'{user} уже админ'
    else:
        data['users'].append(user)
        save_data()
        message = f'Новый админ: {user}'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
async def _delete_admin_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите порядковый номер админа в списке:',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_delete_admin_complete'


@admin_wrap
async def _delete_admin_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@admin_wrap
async def _save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filename = 'card_bot_data.zip'

    with zipfile.ZipFile(filename, 'w') as f:
        for image in data['images']:
            f.write(os.path.join(IMAGE_DIR, image['name']), os.path.join('images', image['name']))
        f.write(DATA_FILE, 'data.json')

    try:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=filename)
    finally:
        os.remove(f.filename)


@admin_wrap
async def _load_data_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Отправьте zip архив c данными и изображениями:',
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_load_data_complete'


@admin_wrap
async def _load_data_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data

    if os.path.exists('old_data'):
        message = 'Архив уже загружается'
    else:
        attachment = update.effective_message.effective_attachment
        file = await attachment.get_file()
        path = await file.download_to_drive()

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

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


@error_wrap
async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action_name = actions.pop(f'{update.effective_user.username}_{update.effective_chat.id}', None)
    if action_name is not None:
        handler = globals().get(action_name)
        if handler is not None:
            await handler(update, context)


@error_wrap
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    handler = globals().get(query.data)
    if handler is not None:
        await handler(update, context)


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    admin_handler = CommandHandler('admin', admin)
    application.add_handler(admin_handler)

    menu_handler = CallbackQueryHandler(menu)
    application.add_handler(menu_handler)

    action_handler = MessageHandler(~filters.COMMAND, action)
    application.add_handler(action_handler)

    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)

    if MODE == 'webhook':
        pass
    else:
        application.run_polling()


# https://amvera.ru/?utm_source=habr&utm_medium=article&utm_campaign=oblako_dlya_botov#rec626926404
# possible inline.
