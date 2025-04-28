from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
import logging
from config import BOT_TOKEN
import sqlite3

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

STATE_ASK_HEIGHT_WEIGHT = 1
STATE_ASK_OUTDOOR = 2
STATE_ASK_POSITION1 = 3
STATE_ASK_BUDGET = 4
STATE_SELECTION = 5


# Команда /start
async def start(update, context):
    button = InlineKeyboardButton(text='Начнем подбор!', callback_data='start_selection')
    keyboard = InlineKeyboardMarkup([[button]])
    await update.message.reply_html(
        f"Привет {update.effective_user.mention_html()}! \nНажимай кнопку и начнем!",
        reply_markup=keyboard
    )


async def start_selection(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == 'start_selection':
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"Введите ваши данные в формате рост/вес [см/кг]."
        )
        return STATE_ASK_HEIGHT_WEIGHT


# Обработка ввода роста и веса
async def ask_height_weight(update, context):
    data = update.message.text
    try:
        height, weight = map(int, data.split("/"))
    except ValueError:
        await update.message.reply_text(
            "Ошибка: Введите данные в формате рост/вес (например, 180/75). "
            "Используйте только числа и символ '/'."
        )
        return STATE_ASK_HEIGHT_WEIGHT

    context.user_data['height'] = height
    context.user_data['weight'] = weight

    return await ask_outdoor(update, context)


async def ask_outdoor(update, context):
    button_indoor = InlineKeyboardButton(text="Зал", callback_data="indoor")
    button_outdoor = InlineKeyboardButton(text="Улица", callback_data="outdoor")
    button_both = InlineKeyboardButton(text="Зал и Улица", callback_data="both")
    keyboard = InlineKeyboardMarkup([[button_indoor], [button_outdoor], [button_both]])

    await update.message.reply_text("Где ты собираешься играть?", reply_markup=keyboard)
    return STATE_ASK_OUTDOOR


async def ask_position(update, context):
    query = update.callback_query
    await query.answer()

    outdoor = query.data
    context.user_data['outdoor'] = outdoor

    button_1_2_3 = InlineKeyboardButton(text="1-2-3", callback_data="1-2-3")
    button_4_5 = InlineKeyboardButton(text="4-5", callback_data="4-5")
    keyboard = InlineKeyboardMarkup([[button_1_2_3], [button_4_5]])

    await query.message.reply_text("На какой позиции ты играешь?", reply_markup=keyboard)
    return STATE_ASK_POSITION1


async def handle_position(update, context):
    query = update.callback_query
    await query.answer()

    position = query.data
    context.user_data['position'] = position

    button_low = InlineKeyboardButton(text="Низкий", callback_data="low_budget")
    button_mid = InlineKeyboardButton(text="Средний", callback_data="mid_budget")
    button_high = InlineKeyboardButton(text="Высокий", callback_data="high_budget")
    keyboard = InlineKeyboardMarkup([[button_low], [button_mid], [button_high]])

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Вы выбрали позицию: {position}. Теперь выберите бюджет:",
        reply_markup=keyboard
    )
    return STATE_ASK_BUDGET


async def handle_budget(update, context):
    query = update.callback_query
    await query.answer()

    budget = query.data
    context.user_data['budget'] = budget

    # await selection(update, context)
    return STATE_SELECTION


async def selection(update, context):
    query = update.callback_query
    await query.answer()
    try:
        budget = None
        if context.user_data.get('budget') == 'low_budget':
            budget = "price <= 120"
        elif context.user_data.get('budget') == 'mid_budget':
            budget = "price <= 225"
        elif context.user_data.get('budget') == 'high_budget':
            pass

        con = sqlite3.connect('kicks.db')
        cur = con.cursor()
        cur.execute(f"SELECT name, price FROM sneakers WHERE {budget}")
        results = cur.fetchall()
        await query.message.reply_text("Идет поиск подходящей пары...")
        if results:
            response = "Рекомендуемые кроссовки:\n"
            for name, price in results:
                response += f"- {name} ({price} $)\n"
        else:
            response = "К сожалению, подходящих кроссовок не найдено."
        await query.edit_message_text(response)
        con.close()
    except Exception as e:
        logger.error(f"Ошибка при работе с базой данных: {e}")
        await query.edit_message_text("Произошла ошибка. Приносим извинения.")

    return ConversationHandler.END


async def help_command(update, context):
    help_text = (
        "Справка по использованию бота:\n"
        "/start - Начать подбор кроссовок.\n"
        "/stop - Прервать текущий диалог.\n"
        "/help - Получить эту справку.\n"
        "\n"
        "Чтобы начать подбор, введите команду /start и следуйте инструкциям на экране.\n"
        "Вы сможете выбрать рост, вес, место игры, позицию и бюджет."
    )
    await update.message.reply_text(help_text)


# Команда /stop
async def stop(update, context):
    await update.message.reply_text("Подбор был прерван.")
    return ConversationHandler.END


# Основная функция
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_selection)],
        states={
            STATE_ASK_HEIGHT_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_height_weight)
            ],
            STATE_ASK_OUTDOOR: [
                CallbackQueryHandler(ask_position)
            ],
            STATE_ASK_POSITION1: [
                CallbackQueryHandler(handle_position)
            ],
            STATE_ASK_BUDGET: [
                CallbackQueryHandler(handle_budget)
            ],
            STATE_SELECTION: [
                CallbackQueryHandler(selection)
            ]
        },
        fallbacks=[CommandHandler('stop', stop)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == '__main__':
    main()
