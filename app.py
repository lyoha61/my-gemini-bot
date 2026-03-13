import asyncio
import os
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import TCPConnector
import google.generativeai as genai
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Секреты
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# Инициализация Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Мы не создаем бота здесь, а создадим его внутри lifespan
bot: Bot = None 
dp = Dispatcher()

@dp.message()
async def handle_message(message: types.Message):
    try:
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        response = await asyncio.to_thread(model.generate_content, message.text)
        text = response.text if response.text else "🤖 Ответ не получен."
        await message.answer(text)
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        await message.answer("⚠️ Ошибка связи с нейросети.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot
    logger.info("Инициализация сессии и DNS-коннектора...")
    
    # Теперь мы создаем сессию ТУТ, когда loop уже запущен
    session = AiohttpSession(
        connector=TCPConnector(family=0, use_dns_cache=False)
    )
    bot = Bot(token=TELEGRAM_TOKEN, session=session, parse_mode=ParseMode.HTML)
    
    logger.info("Попытка запуска бота...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        polling_task = asyncio.create_task(dp.start_polling(bot))
        logger.info("Бот успешно запущен и готов к работе!")
        yield
    finally:
        logger.info("Завершение работы...")
        polling_task.cancel()
        await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"status": "alive"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
