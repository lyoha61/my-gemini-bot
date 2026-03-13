import asyncio
import os
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.client.default import DefaultBotProperties # Добавили новый импорт
import google.generativeai as genai
from fastapi import FastAPI
import uvicorn

# 1. Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Переменные
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# 3. Настройка Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

# 4. Инициализация бота по стандартам aiogram 3.7+
# Теперь настройки передаются через DefaultBotProperties
bot = Bot(
    token=TELEGRAM_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

@dp.message()
async def handle_message(message: types.Message):
    try:
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        
        # Запрос к Gemini
        response = await asyncio.to_thread(model.generate_content, message.text)
        
        text = response.text if response.text else "🤖 Ответ не получен."
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

# 5. Жизненный цикл (Lifespan)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting bot services...")
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    logger.info("Shutting down...")
    polling_task.cancel()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"status": "ok", "message": "Bot is running on Render"}

if __name__ == "__main__":
    # Render автоматически назначает порт в переменную PORT
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
