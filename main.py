import os
import shutil
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging Config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Temporary user session storage
user_data = {}

# Initialize Telegram Application
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

async def process_rendering(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Background task for rendering FFmpeg video without blocking Webhook"""
    user_dir = f"downloads/{user_id}"
    output_path = f"{user_dir}/output.mp4"
    
    try:
        await context.bot.send_message(chat_id=chat_id, text="⚙️ Rendering your Kinetic Scrapbook Reel... Please wait! ⏳")
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_video")

        # FFmpeg Kinetic Command
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-i', user_data[user_id]['image'],
            '-i', user_data[user_id]['audio'],
            '-vf', "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.1)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
            '-c:v', 'libx264', '-t', '5', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest', '-threads', '1',
            output_path
        ]

        proc = await asyncio.create_subprocess_exec(*cmd)
        await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode == 0 and os.path.exists(output_path):
            with open(output_path, 'rb') as video:
                await context.bot.send_video(chat_id=chat_id, video=video, caption="✨ Your CutX Kinetic Reel is Ready!")
        else:
            await context.bot.send_message(chat_id=chat_id, text="❌ FFmpeg failed to generate video.")
            
    except asyncio.TimeoutError:
        await context.bot.send_message(chat_id=chat_id, text="⏳ Processing took too long and timed out.")
    except Exception as e:
        logger.error(f"Rendering failed: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Failed to render reel: {e}")
    finally:
        # CLEANUP Storage & Session
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir, ignore_errors=True)
        user_data.pop(user_id, None)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_dir = f"downloads/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    photo_file = await update.message.photo[-1].get_file()
    img_path = f"{user_dir}/input.jpg"
    await photo_file.download_to_drive(img_path)

    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]['image'] = img_path

    if 'audio' in user_data[user_id]:
        asyncio.create_task(process_rendering(user_id, chat_id, context))
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

    # File size check (Limit to 20MB due to Bot API)
    if audio.file_size and audio.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ Audio file is too large! Please send a file under 20MB.")
        return

    os.makedirs(user_dir, exist_ok=True)
    audio_file = await audio.get_file()
    audio_path = f"{user_dir}/input.mp3"
    await audio_file.download_to_drive(audio_path)

    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]['audio'] = audio_path

    if 'image' in user_data[user_id]:
        asyncio.create_task(process_rendering(user_id, chat_id, context))
    else:
        await update.message.reply_text("✅ Audio received! Now send me a Photo 📸.")

# Event Handlers
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
ptb_app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, handle_audio))

# Modern Lifespan Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    await ptb_app.initialize()
    await ptb_app.start()
    if WEBHOOK_URL:
        clean_url = WEBHOOK_URL.rstrip('/')
        webhook_path = f"{clean_url}/webhook"
        logger.info(f"Setting Webhook URL: {webhook_path}")
        await ptb_app.bot.set_webhook(url=webhook_path)
    yield
    await ptb_app.stop()
    await ptb_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
async def index():
    return {"status": "CutX Bot is Running online!"}
    
