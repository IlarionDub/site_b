# python3 bot.py

import logging
import os
import re
from dotenv import load_dotenv
from telegram import Update, Message, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Завантаження .env
load_dotenv()

# Логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токени
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.error("❌ TELEGRAM_BOT_TOKEN або OPENAI_API_KEY не знайдено")
    exit()

# OpenAI клієнт
client = OpenAI(api_key=OPENAI_API_KEY)

# Збереження повідомлень
chat_message_history = {}  # {chat_id: [msg_id1, msg_id2]}


# 🔧 Функція для екранування MarkdownV2
def escape_markdown(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)


# 🧹 Видалення попередніх повідомлень
async def delete_old_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if chat_id in chat_message_history:
        for msg_id in chat_message_history[chat_id]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logger.warning(f"⚠️ Видалення не вдалося: {e}")
        chat_message_history[chat_id] = []


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await delete_old_messages(context, chat_id)

    try:
        await update.message.delete()
    except:
        pass

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text="👋 Привіт! Надішли завдання, і я згенерую Java-код з патернами проєктування."
    )
    chat_message_history[chat_id] = [sent.message_id]


# Обробка звичайних повідомлень
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_msg: Message = update.message
    user_text = user_msg.text
    logger.info(f"[{chat_id}] Вхідне повідомлення: {user_text}")

    await delete_old_messages(context, chat_id)

    try:
        await user_msg.delete()
    except:
        pass

    processing = await context.bot.send_message(chat_id=chat_id, text="⏳ Обробляю запит...")
    msg_ids = [processing.message_id]

    try:
        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "Ти – експерт з програмування на Java та патернів проєктування. "
                    "Згенеруй повний, готовий до використання Java-код. Без коментарів, без описів, лише код. Окрім кода ніякі коментарі або лапки, тільки код"
                )
            },
            {
                "role": "user",
                "content": f"Згенеруй Java-код для: {user_text}"
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=prompt_messages,
            temperature=0.2,
        )

        generated_code = response.choices[0].message.content.strip()

        try:
            await processing.delete()
        except:
            pass

        if len(generated_code) < 4000:
            try:
                formatted = f"```java\n{escape_markdown(generated_code)}\n```"
                sent = await context.bot.send_message(chat_id=chat_id, text=formatted, parse_mode="MarkdownV2")
            except Exception as e_md:
                logger.warning(f"⚠️ MarkdownV2 не спрацював: {e_md}")
                sent = await context.bot.send_message(chat_id=chat_id, text=generated_code)
        else:
            with open("code.java", "w", encoding="utf-8") as f:
                f.write(generated_code)
            with open("code.java", "rb") as f:
                sent = await context.bot.send_document(chat_id=chat_id, document=InputFile(f, filename="code.java"))

        msg_ids.append(sent.message_id)

    except Exception as e:
        logger.error(f"❌ Помилка: {e}")
        sent = await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Сталася помилка: {e}")
        msg_ids.append(sent.message_id)

    chat_message_history[chat_id] = msg_ids


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🚀 Бот запущений!")
    application.run_polling()


if __name__ == "__main__":
    main()