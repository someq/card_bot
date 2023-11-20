import logging
import os
import traceback as tb
import random
import json
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


if os.path.exists('data.json'):
    with open('data.json') as f:
        data = json.load(f)
else:
    data = {
        'users': [],
        'images': []
    }
    with open('data.json', 'w') as f:
        json.dump(data, f)


def save_data():
    with open('data.json', 'w') as f:
        json.dump(data, f)


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
        text="Привет, позолоти ручку?!",
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
async def _get_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image = random.choice(data['images'])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=image['url'])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=image['text'])


@admin_wrap
async def _list_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(data['images']) > 0:
        message = '\n'.join(f"{i + 1}. {image['url']} {image['text']}" for i, image in enumerate(data['images']))
    else:
        message = 'Колода пуста'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, disable_web_page_preview=True)


@admin_wrap
async def _add_card_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите ссылку на изображение и текст через пробел, например:\n'
             'https://example.com/image.jpg Моя красивая карта',
        disable_web_page_preview=True,
    )
    actions[f'{update.effective_user.username}_{update.effective_chat.id}'] = '_add_card_complete'


@admin_wrap
async def _add_card_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split(' ', maxsplit=1)
    url = parts[0].strip()
    text = parts[1].strip() if len(parts) > 1 else ""
    data['images'].append({'url': url, 'text': text})
    save_data()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Новая карта:\nСсылка: {url}\nТекст: {text}',
    )


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
        id = int(update.message.text.strip())
        card = data['images'].pop(id - 1)
    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Неправильный номер')
    except IndexError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Номера нет в списке')
    else:
        save_data()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Удалена карта:\nСсылка: {card["url"]}\nТекст: {card["text"]}',
        )

@admin_wrap
async def _list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@admin_wrap
async def _add_admin_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@admin_wrap
async def _admin_admin_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@admin_wrap
async def _remove_admin_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@admin_wrap
async def _remove_admin_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@admin_wrap
async def _save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@admin_wrap
async def _load_data_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@admin_wrap
async def _load_data_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


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


# https:/-/amvera.ru/?utm_source=habr&utm_medium=article&utm_campaign=oblako_dlya_botov#rec626926404
# possible inline.
# possible login with password
# possible actions with multi-message dialog
# possible ids for images
