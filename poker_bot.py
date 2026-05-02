import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import os

# Токен берётся из переменной окружения (Railway → Variables → BOT_TOKEN)
BOT_TOKEN = os.environ.get("8548385762:AAGwnU739zrnaRLRhI235aC8E8jGToilWy0")

MIN_PLAYERS = 5
MAX_PLAYERS = 9

logging.basicConfig(level=logging.INFO)

# Хранилище игр: { chat_id: { message_id, players: [] } }
games = {}


def build_message(players: list) -> tuple[str, InlineKeyboardMarkup]:
    count = len(players)

    if count == 0:
        status = "⏳ Пока никого нет — будь первым!"
    elif count < MIN_PLAYERS:
        status = f"⏳ Нужно ещё {MIN_PLAYERS - count} чел. чтобы игра состоялась"
    else:
        status = "✅ Покер состоится!"

    players_text = ""
    suits = ["♠", "♥", "♦", "♣", "♠", "♥", "♦", "♣", "♠"]
    for i, name in enumerate(players):
        players_text += f"\n{i+1}. {suits[i]} {name}"

    text = (
        f"🃏 *Покер сегодня!*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Записалось: *{count} / {MAX_PLAYERS}*\n"
        f"{status}"
        f"{players_text if players_text else chr(10) + '_(список пуст)_'}"
    )

    keyboard = []
    if count < MAX_PLAYERS:
        keyboard.append(InlineKeyboardButton("✋ Я играю", callback_data="join"))
    keyboard.append(InlineKeyboardButton("❌ Не иду", callback_data="leave"))

    return text, InlineKeyboardMarkup([keyboard])


async def poker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Если игра уже есть — удаляем старое сообщение
    if chat_id in games:
        try:
            await context.bot.delete_message(chat_id, games[chat_id]["message_id"])
        except Exception:
            pass

    games[chat_id] = {"players": [], "message_id": None}

    text, markup = build_message([])
    msg = await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    games[chat_id]["message_id"] = msg.message_id

    # Удаляем команду /poker из чата
    try:
        await update.message.delete()
    except Exception:
        pass


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    user = query.from_user
    name = user.first_name
    if user.last_name:
        name += f" {user.last_name}"

    if chat_id not in games:
        await query.answer("Сначала создай игру командой /poker", show_alert=True)
        return

    players = games[chat_id]["players"]

    if query.data == "join":
        if name in players:
            await query.answer("Ты уже в списке! 👀", show_alert=True)
            return
        if len(players) >= MAX_PLAYERS:
            await query.answer("Стол заполнен!", show_alert=True)
            return
        players.append(name)
        await query.answer("Ты записан! Удачи 🃏")

    elif query.data == "leave":
        if name not in players:
            await query.answer("Тебя и так нет в списке", show_alert=True)
            return
        players.remove(name)
        await query.answer("Ты вышел из игры")

    text, markup = build_message(players)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("poker", poker_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ Бот запущен! Нажми Ctrl+C чтобы остановить.")
    app.run_polling()


if __name__ == "__main__":
    main()
