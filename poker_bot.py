import logging
import os
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

MIN_PLAYERS = 5
MAX_PLAYERS = 9

POKER_IMAGE = "https://images.unsplash.com/photo-1541278107931-e006523892df?w=800"

logging.basicConfig(level=logging.INFO)

# { chat_id: { message_id, yes: [], maybe: [], no: [], date: "YYYY-MM-DD" } }
games = {}


def get_today():
    return datetime.now().strftime("%Y-%m-%d")


def get_or_create_game(chat_id):
    today = get_today()
    if chat_id not in games or games[chat_id]["date"] != today:
        # Новый день — сбрасываем
        games[chat_id] = {"yes": [], "maybe": [], "no": [], "message_id": None, "date": today}
    return games[chat_id]


def build_message(yes: list, maybe: list, no: list):
    count = len(yes)

    if count == 0:
        status = "⏳ Ждём игроков..."
    elif count < MIN_PLAYERS:
        status = f"⏳ Нужно ещё {MIN_PLAYERS - count} чел. чтобы игра состоялась"
    else:
        status = "✅ Покер состоится!"

    suits = ["♠", "♥", "♦", "♣", "♠", "♥", "♦", "♣", "♠"]

    yes_text = ""
    for i, name in enumerate(yes):
        yes_text += f"\n  {i+1}. {suits[i % 4]} {name}"

    maybe_text = ""
    for name in maybe:
        maybe_text += f"\n  🤔 {name}"

    no_text = ""
    for name in no:
        no_text += f"\n  ❌ {name}"

    today = datetime.now().strftime("%d.%m.%Y")

    text = (
        f"🃏 Покер — {today}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{status}\n\n"
        f"✅ Идут ({len(yes)}/{MAX_PLAYERS}):{yes_text if yes_text else ' —'}\n\n"
        f"🤔 Возможно ({len(maybe)}):{maybe_text if maybe_text else ' —'}\n\n"
        f"❌ Не идут ({len(no)}):{no_text if no_text else ' —'}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Иду", callback_data="yes"),
            InlineKeyboardButton("🤔 Возможно", callback_data="maybe"),
            InlineKeyboardButton("❌ Не иду", callback_data="no"),
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


async def poker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_or_create_game(chat_id)

    # Удаляем старое сообщение если есть
    if game["message_id"]:
        try:
            await context.bot.delete_message(chat_id, game["message_id"])
        except Exception:
            pass

    text, markup = build_message(game["yes"], game["maybe"], game["no"])

    # Отправляем с картинкой
    try:
        msg = await update.message.reply_photo(
            photo=POKER_IMAGE,
            caption=text,
            reply_markup=markup
        )
    except Exception:
        msg = await update.message.reply_text(text, reply_markup=markup)

    game["message_id"] = msg.message_id

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

    game = get_or_create_game(chat_id)

    # Убираем из всех списков (смена голоса)
    for key in ["yes", "maybe", "no"]:
        if name in game[key]:
            game[key].remove(name)

    if query.data == "yes":
        if len(game["yes"]) >= MAX_PLAYERS:
            await query.answer("Стол заполнен!", show_alert=True)
            return
        game["yes"].append(name)
        await query.answer("Ты идёшь! 🃏")

    elif query.data == "maybe":
        game["maybe"].append(name)
        await query.answer("Понял, возможно придёшь 🤔")

    elif query.data == "no":
        game["no"].append(name)
        await query.answer("Жаль, в другой раз! ❌")

    text, markup = build_message(game["yes"], game["maybe"], game["no"])

    # Обновляем caption у фото-сообщения
    try:
        await query.edit_message_caption(caption=text, reply_markup=markup)
    except Exception:
        try:
            await query.edit_message_text(text, reply_markup=markup)
        except Exception:
            pass


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("poker", poker_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
