import asyncio
import os
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.client.default import DefaultBotProperties
import google.generativeai as genai
from fastapi import FastAPI
import uvicorn

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Переменные окружения (Render берет их из Settings -> Env Vars)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# 3. Инициализация Gemini
genai.configure(api_key=GEMINI_KEY)

# Авто-проверка доступных моделей (появится в логах Render при запуске)
logger.info("--- ПРОВЕРКА ДОСТУПНЫХ МОДЕЛЕЙ ---")
try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    for model_name in available_models:
        logger.info(f"Доступная модель: {model_name}")
except Exception as e:
    logger.error(f"Не удалось получить список моделей: {e}")

# Выбираем модель (Gemini 2.0 Flash - стандарт 2026 года)
# Если в логах увидишь другое имя, просто замени строку ниже
MODEL_NAME = 'gemini-2.0-flash' 
model = genai.GenerativeModel(MODEL_NAME)

# 4. Инициализация бота
bot = Bot(
    token=TELEGRAM_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Обработчик сообщений
@dp.message()
async def handle_message(message: types.Message):
    try:
        # Показываем, что бот печатает
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        
        # Запрос к нейросети
        response = await asyncio.to_thread(model.generate_content, message.text)
        
        # Проверка ответа
        if response.text:
            await message.answer(response.text)
        else:
            await message.answer("🤖 Бот получил пустой ответ от нейросети.")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        # Выводим краткую ошибку в чат для диагностики
        await message.answer(f"⚠️ Ошибка: {str(e)[:50]}...")

# 5. Управление запуском (Lifespan)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Запуск бота {MODEL_NAME}...")
    # Очищаем старые сообщения, чтобы бот не спамил при включении
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск процесса опроса Telegram (Polling)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    logger.info("Бот онлайн и готов к работе!")
    
    yield
    
    logger.info("Выключение бота...")
    polling_task.cancel()
    await bot.session.close()

# 6. FastAPI сервер
app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health_check():
    return {"status": "ok", "model": MODEL_NAME}

if __name__ == "__main__":
    # Render сам назначит порт
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
