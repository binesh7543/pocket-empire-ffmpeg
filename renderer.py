import os
import shutil
import asyncio
import logging
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def process_rendering(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_sessions: dict):
    user_dir = f"downloads/{user_id}"
    output_path = f"{user_dir}/output.mp4"

    try:
        await context.bot.send_message(chat_id=chat_id, text="⚙️ Rendering your Kinetic Scrapbook Reel... Please wait! ⏳")
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_video")

        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-i', user_sessions[user_id]['image'],
            '-i', user_sessions[user_id]['audio'],
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
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir, ignore_errors=True)
        user_sessions.pop(user_id, None)
