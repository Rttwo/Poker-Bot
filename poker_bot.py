import logging
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")

MIN_PLAYERS = 5
MAX_PLAYERS = 9
POKER_IMAGE = "https://i.postimg.cc/nzGR9GWG/poker-image.jpg"

logging.basicConfig(level=logging.INFO)

# { chat_id: { date_str: { message_id, yes, maybe, no } } }
games = {}

WAITING_CUSTOM_DATE = 1


def get_game(chat_id, date_str):
    if chat_id not in games:
        games[chat_id] = {}
    if date_str not in games[chat_id]:
        games[chat_id][date_str] = {"yes": [], "maybe": [], "no": [], "message_id": None}
    return games[chat_id][date_str]


def build_message(yes, maybe, no, date_str):
    count = len(yes)

    # Форматируем дату красиво
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        if d.date() == today:
            date_label = f"сегодня {d.strftime('%d.%m')}"
        elif d.date() == tomorrow:
            date_label = f"завтра {d.strftime('%d.%m')}"
        else:
            date_label = d.strftime('%d.%m.%Y')
    except:
        date_label = date_str

    if count == 0:
        status = "⏳ Ждём игроков..."
    elif count < MIN_PLAYERS:
        status = f"⏳ Нужно ещё {MIN_PLAYERS - count} чел. чтобы игра состоялась"
    else:
        status = "✅ Покер состоится!"

    suits = ["♠", "♥", "♦", "♣", "♠", "♥", "♦", "♣", "♠"]

    yes_text = "".join(f"\n  {i+1}. {suits[i % 4]} {n}" for i, n in enumerate(yes)) or " —"
    maybe_text = "".join(f"\n  🤔 {n}" for n in maybe) or " —"
    no_text = "".join(f"\n  ❌ {n}" for n in no) or " —"

    text = (
        f"🃏 Покер — {date_label}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{status}\n\n"
        f"✅ Идут ({len(yes)}/{MAX_PLAYERS}):{yes_text}\n\n"
        f"🤔 Возможно ({len(maybe)}):{maybe_text}\n\n"
        f"❌ Не идут ({len(no)}):{no_text}"
    )

    keyboard = [[
        InlineKeyboardButton("✅ Иду", callback_data=f"yes|{date_str}"),
        InlineKeyboardButton("🤔 Возможно", callback_data=f"maybe|{date_str}"),
        InlineKeyboardButton("❌ Не иду", callback_data=f"no|{date_str}"),
    ]]

    return text, InlineKeyboardMarkup(keyboard)


async def poker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    keyboard = [[
        InlineKeyboardButton(f"Сегодня {today.strftime('%d.%m')}", callback_data=f"date|{today.strftime('%Y-%m-%d')}"),
        InlineKeyboardButton(f"Завтра {tomorrow.strftime('%d.%m')}", callback_data=f"date|{tomorrow.strftime('%Y-%m-%d')}"),
    ], [
        InlineKeyboardButton(f"{day_after.strftime('%d.%m')}", callback_data=f"date|{day_after.strftime('%Y-%m-%d')}"),
        InlineKeyboardButton("📅 Другая дата", callback_data="date|custom"),
    ]]

    msg = await update.message.reply_text(
        "🃏 На какой день планируем покер?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Сохраняем id сообщения выбора даты чтобы потом удалить
    if "date_picker_msg" not in context.chat_data:
        context.chat_data["date_picker_msg"] = {}
    context.chat_data["date_picker_msg"][update.effective_chat.id] = msg.message_id

    try:
        await update.message.delete()
    except:
        pass


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    _, date_str = query.data.split("|", 1)

    # Удаляем сообщение с выбором даты
    try:
        await query.message.delete()
    except:
        pass

    if date_str == "custom":
        msg = await context.bot.send_message(
            chat_id,
            "📅 Введи дату в формате ДД.ММ\nНапример: 25.12"
        )
        context.chat_data["waiting_date_msg"] = msg.message_id
        context.chat_data["waiting_custom_date"] = True
        return

    await send_poker_poll(context, chat_id, date_str)


async def handle_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.chat_data.get("waiting_custom_date"):
        return

    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Удаляем сообщение с просьбой ввести дату
    try:
        await context.bot.delete_message(chat_id, context.chat_data.get("waiting_date_msg"))
    except:
        pass

    try:
        await update.message.delete()
    except:
        pass

    try:
        day, month = text.split(".")
        year = datetime.now().year
        date_obj = datetime(year, int(month), int(day))
        # Если дата уже прошла — берём следующий год
        if date_obj.date() < datetime.now().date():
            date_obj = datetime(year + 1, int(month), int(day))
        date_str = date_obj.strftime("%Y-%m-%d")
    except:
        err = await context.bot.send_message(chat_id, "❌ Неверный формат. Попробуй ещё раз: /poker")
        context.chat_data["waiting_custom_date"] = False
        return

    context.chat_data["waiting_custom_date"] = False
    await send_poker_poll(context, chat_id, date_str)


async def send_poker_poll(context, chat_id, date_str):
    game = get_game(chat_id, date_str)

    # Удаляем старое сообщение если есть
    if game["message_id"]:
        try:
            await context.bot.delete_message(chat_id, game["message_id"])
        except:
            pass

    text, markup = build_message(game["yes"], game["maybe"], game["no"], date_str)

    try:
        msg = await context.bot.send_photo(
            chat_id,
            photo=POKER_IMAGE,
            caption=text,
            reply_markup=markup
        )
    except:
        msg = await context.bot.send_message(chat_id, text, reply_markup=markup)

    game["message_id"] = msg.message_id


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    action, date_str = query.data.split("|", 1)

    user = query.from_user
    name = user.first_name
    if user.last_name:
        name += f" {user.last_name}"

    game = get_game(chat_id, date_str)

    # Убираем из всех списков
    for key in ["yes", "maybe", "no"]:
        if name in game[key]:
            game[key].remove(name)

    if action == "yes":
        if len(game["yes"]) >= MAX_PLAYERS:
            await query.answer("Стол заполнен!", show_alert=True)
            return
        game["yes"].append(name)
        await query.answer("Ты идёшь! 🃏")
    elif action == "maybe":
        game["maybe"].append(name)
        await query.answer("Понял, возможно придёшь 🤔")
    elif action == "no":
        game["no"].append(name)
        await query.answer("Жаль, в другой раз! ❌")

    text, markup = build_message(game["yes"], game["maybe"], game["no"], date_str)

    try:
        await query.edit_message_caption(caption=text, reply_markup=markup)
    except:
        try:
            await query.edit_message_text(text, reply_markup=markup)
        except:
            pass


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("poker", poker_command))
    app.add_handler(CallbackQueryHandler(date_selected, pattern="^date\\|"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(yes|maybe|no)\\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_date))
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
