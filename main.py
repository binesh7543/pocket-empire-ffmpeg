import os
import asyncio
import subprocess
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging Config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = FastAPI()

# Initialize Telegram Application
ptb_app = Application.builder().token(BOT_TOKEN).build()

# Store user session data (Temporary MVP)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Kinetic Scrapbook Reel Bot!\n\n"
        "Please send me:\n"
        "1. Background Image / Photo 📸\n"
        "2. Audio track / Song 🎵\n\n"
        "I will process it into a Kinetic Scrapbook edit!"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo_file = await update.message.photo[-1].get_file()
    
    os.makedirs(f"downloads/{user_id}", exist_ok=True)
    img_path = f"downloads/{user_id}/input.jpg"
    await photo_file.download_to_drive(img_path)
    
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]['image'] = img_path
    
    await update.message.reply_text("✅ Image received! Now send me an Audio file (.mp3).")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    audio = update.message.audio or update.message.voice or update.message.document
    
    if not audio:
        await update.message.reply_text("Please send a valid audio file.")
        return

    os.makedirs(f"downloads/{user_id}", exist_ok=True)
    audio_file = await audio.get_file()
    audio_path = f"downloads/{user_id}/input.mp3"
    await audio_file.download_to_drive(audio_path)
    
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]['audio'] = audio_path

    if 'image' in user_data[user_id]:
        await update.message.reply_text("⚙️ Rendering your Kinetic Scrapbook Reel... Please wait! ⏳")
        output_path = f"downloads/{user_id}/output.mp4"
        
        # FFmpeg Kinetic MVP Command (Resizing, 1080x1920 Reel, Single thread for free tier)
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-i', user_data[user_id]['image'],
            '-i', user_data[user_id]['audio'],
            '-vf', "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.1)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
            '-c:v', 'libx264', '-t', '5', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192',
            '-shortest', '-threads', '1',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True)
            with open(output_path, 'rb') as video:
                await update.message.reply_video(video=video, caption="✨ Your Kinetic Reel is Ready!")
        except Exception as e:
            logger.error(f"Rendering failed: {e}")
            await update.message.reply_text(f"❌ Failed to render reel: {e}")
    else:
        await update.message.reply_text("⚠️ Please send a Photo first!")

# Telegram Event Handlers
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
ptb_app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, handle_audio))

@app.on_event("startup")
async def startup():
    await ptb_app.initialize()
    await ptb_app.start()
    if WEBHOOK_URL:
        await ptb_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def index():
    return {"status": "Kinetic Scrapbook Bot is Running online!"}
