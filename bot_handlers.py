import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from renderer import process_rendering

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# RAM-based session storage
user_sessions = {}

ptb_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ *Welcome to CutX Reel Bot!* ⚡\n\n"
        "Send me:\n"
        "1. Background Image / Photo 📸\n"
        "2. Audio track / Song 🎵\n\n"
        "(You can send them in any order!)",
        parse_mode="Markdown"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_dir = f"downloads/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    photo_file = await update.message.photo[-1].get_file()
    img_path = f"{user_dir}/input.jpg"
    await photo_file.download_to_drive(img_path)

    user_sessions[user_id] = user_sessions.get(user_id, {})
    user_sessions[user_id]['image'] = img_path

    if 'audio' in user_sessions[user_id]:
        asyncio.create_task(process_rendering(user_id, chat_id, context, user_sessions))
    else:
        await update.message.reply_text("✅ Image received! Now send me an Audio file (.mp3).")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_dir = f"downloads/{user_id}"
    audio = update.message.audio or update.message.voice or update.message.document

    if not audio:
        await update.message.reply_text("Please send a valid audio file.")
        return

    if audio.file_size and audio.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ Audio file is too large! Please send a file under 20MB.")
        return

    os.makedirs(user_dir, exist_ok=True)
    audio_file = await audio.get_file()
    audio_path = f"{user_dir}/input.mp3"
    await audio_file.download_to_drive(audio_path)

    user_sessions[user_id] = user_sessions.get(user_id, {})
    user_sessions[user_id]['audio'] = audio_path

    if 'image' in user_sessions[user_id]:
        asyncio.create_task(process_rendering(user_id, chat_id, context, user_sessions))
    else:
        await update.message.reply_text("✅ Audio received! Now send me a Photo 📸.")

ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
ptb_app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, handle_audio))
