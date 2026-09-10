import os
import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from telegram import Update

from bot_handlers import ptb_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(3):
        try:
            await ptb_app.initialize()
            break
        except Exception as e:
            logger.warning(f"Telegram init attempt {attempt+1} failed: {e}")
            if attempt == 2:
                raise
            await asyncio.sleep(3)

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

@app.api_route("/", methods=["GET", "HEAD"])
async def index():
    return {"status": "CutX Bot is Running online!"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
