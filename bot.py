import logging
import json
import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiohttp import web

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv("API_TOKEN")  # токен из Render → Environment
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")  # Render сам создаёт этот URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

DATA_FILE = "data.json"

# --- ЛОГИ ---
logging.basicConfig(level=logging.INFO)

# --- ДАННЫЕ ---
data = {
    "password": "fish",
    "admin_password": "2202",
    "homework": "ДЗ пока не задано",
    "authorized_users": []
}

# Загружаем сохраненные данные
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data.update(json.load(f))


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- СОЗДАЕМ БОТА ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 Посмотреть текущее ДЗ")],
            [KeyboardButton(text="✏️ Задать новое ДЗ")]
        ],
        resize_keyboard=True
    )

def get_group_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 Посмотреть ДЗ", callback_data="show_hw")]
        ]
    )


# --- ХАНДЛЕРЫ ---

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("Привет! Введи пароль:")


@dp.message(lambda m: m.chat.type == "private")
async def handle_private(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Если пользователь уже авторизован — кнопки работают
    if user_id in data["authorized_users"]:
        if text == "📖 Посмотреть текущее ДЗ":
            await message.answer(f"Текущее ДЗ: {data['homework']}", reply_markup=get_main_keyboard())
            return

        if text == "✏️ Задать новое ДЗ":
            await message.answer("Отправь новый текст ДЗ:", reply_markup=types.ReplyKeyboardRemove())
            dp.message.register(set_homework, lambda m: m.chat.type == "private")
            return

        # Любой другой текст считаем новым ДЗ
        data["homework"] = text
        save_data()
        await message.answer(f"ДЗ установлено: {data['homework']}", reply_markup=get_main_keyboard())
        return

    # --- проверка паролей ---
    if text == data["password"]:
        data["authorized_users"].append(user_id)
        save_data()
        await message.answer("Пароль верный! Теперь можешь управлять ДЗ.", reply_markup=get_main_keyboard())
        return

    if text == data["admin_password"]:
        await message.answer("Админ пароль верный! Напиши новый обычный пароль:", reply_markup=types.ReplyKeyboardRemove())
        dp.message.register(change_password, lambda m: m.chat.type == "private")
        return

    await message.answer("неправильно шалунишка")


async def set_homework(message: Message):
    data["homework"] = message.text
    save_data()
    await message.answer(f"ДЗ установлено: {data['homework']}", reply_markup=get_main_keyboard())
    dp.message.unregister(set_homework)


async def change_password(message: Message):
    data["password"] = message.text.strip()
    save_data()
    await message.answer(f"Пароль успешно изменен на: {data['password']}", reply_markup=get_main_keyboard())
    dp.message.unregister(change_password)


@dp.message(lambda m: m.chat.type in ["group", "supergroup"])
async def handle_group(message: Message):
    text = message.text.lower()
    trigger_words = ["дз", "что задали", "что задавали", "какое дз", "что задали?"]

    if any(word in text for word in trigger_words):
        await message.reply("Нажми, чтобы посмотреть ДЗ:", reply_markup=get_group_inline_keyboard())


@dp.callback_query(F.data == "show_hw")
async def callback_show_hw(callback: CallbackQuery):
    await callback.message.reply(f"Вот ДЗ: {data['homework']}")
    await callback.answer()


# --- ЗАПУСК через webhook ---
async def on_startup(app):
    logging.info(f"Устанавливаем webhook: {WEBHOOK_URL}")
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(app):
    logging.info("Удаляем webhook")
    await bot.delete_webhook()


async def main():
    if not API_TOKEN:
        print("❌ ОШИБКА: Не найден API_TOKEN!")
        return

    app = web.Application()
    dp.setup_webhook(app, path=WEBHOOK_PATH)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.getenv("PORT", 10000))  # Render даст порт в переменной PORT
    logging.info(f"Запускаем сервер на порту {port}")
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    asyncio.run(main())