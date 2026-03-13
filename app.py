import asyncio
import os
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatAction, ParseMode
import google.generativeai as genai
from fastapi import FastAPI
import uvicorn

# 1. Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Переменные (Render возьмет их из Environment Variables)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# 3. Настройка Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 4. Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

@dp.message()
async def handle_message(message: types.Message):
    try:
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        
        # Запрос к Gemini в отдельном потоке
        response = await asyncio.to_thread(model.generate_content, message.text)
        
        text = response.text if response.text else "🤖 Ответ не получен."
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

# 5. Жизненный цикл через Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting bot...")
    # На Render Polling работает отлично
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    logger.info("Stopping bot...")
    polling_task.cancel()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    # Render автоматически назначает PORT, берем его из системы
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
