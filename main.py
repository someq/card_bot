import logging
import os
import traceback as tb
import random
import json
from datetime import datetime, timedelta
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


with open('data.json') as f:
    # create data if it does not exist
    data = json.load(f)


# {users login + last time}
#  actions progress
actions = {
    # 'username': {
    #     'login': 'datetime',
    #     'new_image': {
    #         'url': ...,
    #         'text': ...
    #     },
    #     'new_user': {
    #         'username': ...,
    #         'password': ...,
    #         'password_confirm': ...,
    #     }
    # }
}


def error_wrap(func, exc_types=None):
    if exc_types is None:
        exc_types = (Exception,)

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await func(update, context)
        except exc_types as e:
            error = tb.format_exc()
            await context.bot.send_message(chat_id=update.effective_chat.id, text=error)
            logger.error(error)

    return wrapper


_user_menu = InlineKeyboardMarkup([
    [
        InlineKeyboardButton('Получить изображение', callback_data='_get_image'),
    ],
])


_admin_menu = InlineKeyboardMarkup([
    [
        InlineKeyboardButton('Список изображений', callback_data='_list_images'),
        InlineKeyboardButton('Добавить изображение', callback_data='_add_image'),
        InlineKeyboardButton('Удалить изображение', callback_data='_delete_image'),
    ],
    [
        InlineKeyboardButton('Список админов', callback_data='_list_admins'),
        InlineKeyboardButton('Добавить админа', callback_data='_add_admin'),
        InlineKeyboardButton('Удалить админа', callback_data='_delete_admin'),
    ],
    [
        InlineKeyboardButton('Скачать данные', callback_data='_export_data'),
        InlineKeyboardButton('Загрузить данные', callback_data='_import_data'),
    ],
])


@error_wrap
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Привет, я тестовый бот для отправки изображений с подписями",
        reply_markup=_user_menu,
    )


@error_wrap
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = [user['username'] for user in data['users']]
    if update.effective_user.username in users:
        # check last users login time.
        # if more than ..., ask password
        # if password is correct - update last login and allow menu
        # for all actions check login time and does not allow if is not logged.
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Привет, {update.effective_user.username}',
            reply_markup=_admin_menu,
        )
    else:
        await unknown(update, context)


@error_wrap
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Неизвестная команда',
    )


async def _get_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image = random.choice(data['images'])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=image['url'])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=image['text'])


@error_wrap
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    print(query.data)
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

    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)

    if MODE == 'webhook':
        pass
    else:
        application.run_polling()


# https:/-/amvera.ru/?utm_source=habr&utm_medium=article&utm_campaign=oblako_dlya_botov#rec626926404
# possible inline.
