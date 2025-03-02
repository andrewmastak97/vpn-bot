import os
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from database import (
    init_db, add_user, get_user, add_subscription,
    get_active_subscription, save_wireguard_config,
    get_expired_subscriptions, deactivate_subscription,
    extend_subscription
)
from wireguard import create_client_config
from yookassa import Configuration, Payment

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Настройка YooKassa
Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

# Константы для цен и скидок
PRICE_MONTH = Decimal(os.getenv("PRICE_MONTH", "399"))
DISCOUNT_3_MONTHS = Decimal(os.getenv("DISCOUNT_3_MONTHS", "5"))
DISCOUNT_6_MONTHS = Decimal(os.getenv("DISCOUNT_6_MONTHS", "10"))
DISCOUNT_12_MONTHS = Decimal(os.getenv("DISCOUNT_12_MONTHS", "20"))

# Список администраторов
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

def calculate_price(months: int) -> Decimal:
    """Рассчитывает цену с учетом скидки"""
    base_price = PRICE_MONTH * months
    if months >= 12:
        discount = DISCOUNT_12_MONTHS
    elif months >= 6:
        discount = DISCOUNT_6_MONTHS
    elif months >= 3:
        discount = DISCOUNT_3_MONTHS
    else:
        discount = 0
    
    return base_price * (1 - discount / 100)

def get_subscription_keyboard() -> types.InlineKeyboardMarkup:
    """Создает клавиатуру с тарифами"""
    builder = InlineKeyboardBuilder()
    
    plans = [
        ("1 месяц", "buy_1"),
        ("3 месяца (-5%)", "buy_3"),
        ("6 месяцев (-10%)", "buy_6"),
        ("12 месяцев (-20%)", "buy_12")
    ]
    
    for label, callback_data in plans:
        builder.button(text=label, callback_data=callback_data)
    
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username)
        
    active_sub = await get_active_subscription(message.from_user.id)
    
    if not active_sub:
        text = (
            "👋 Добро пожаловать в GadgetBar VPN-бот!\n\n"
            "🎁 Получите бесплатный тестовый период на 1 месяц\n"
            "или выберите один из тарифов:"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="🎁 Получить тестовый период", callback_data="trial")
        builder.button(text="💳 Выбрать тариф", callback_data="show_plans")
        builder.adjust(1)
        await message.answer(text, reply_markup=builder.as_markup())
    else:
        await show_subscription_status(message.from_user.id)

@dp.callback_query(lambda c: c.data == "trial")
async def process_trial(callback: CallbackQuery):
    """Обработка запроса на тестовый период"""
    user_id = callback.from_user.id
    active_sub = await get_active_subscription(user_id)
    
    if active_sub:
        await callback.answer("У вас уже есть активная подписка!", show_alert=True)
        return
    
    # Создаем тестовую подписку
    await add_subscription(
        user_id=user_id,
        subscription_type="trial",
        duration_months=1,
        payment_id="trial",
        is_trial=True
    )
    
    # Генерируем конфигурацию WireGuard
    private_key, public_key, config, qr_config = await create_client_config(user_id)
    await save_wireguard_config(user_id, private_key, public_key, config)
    
    # Отправляем конфигурацию
    text = (
        "✅ Тестовый период активирован!\n\n"
        "📱 Выберите вашу операционную систему для получения инструкций:"
    )
    
    builder = InlineKeyboardBuilder()
    systems = [
        ("Windows", "config_windows"),
        ("MacOS", "config_macos"),
        ("Linux", "config_linux"),
        ("iOS", "config_ios"),
        ("Android", "config_android")
    ]
    
    for label, callback_data in systems:
        builder.button(text=label, callback_data=f"{callback_data}_{user_id}")
    
    builder.adjust(2)
    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "show_plans")
async def show_plans(callback: CallbackQuery):
    """Показывает доступные тарифы"""
    text = "Выберите подходящий тариф:"
    await callback.message.answer(text, reply_markup=get_subscription_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    """Обработка покупки подписки"""
    months = int(callback.data.split("_")[1])
    price = calculate_price(months)
    
    payment = Payment.create({
        "amount": {
            "value": str(price),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{(await bot.me()).username}"
        },
        "capture": True,
        "description": f"VPN подписка на {months} мес.",
        "metadata": {
            "user_id": callback.from_user.id,
            "months": months
        }
    })
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Оплатить",
        url=payment.confirmation.confirmation_url
    )
    
    text = (
        f"💳 Оплата подписки на {months} месяцев\n"
        f"Сумма к оплате: {price} руб.\n\n"
        "Для оплаты нажмите кнопку ниже:"
    )
    
    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()

async def show_subscription_status(user_id: int):
    """Показывает статус подписки"""
    sub = await get_active_subscription(user_id)
    if not sub:
        text = "У вас нет активной подписки."
    else:
        end_date = datetime.fromisoformat(sub["end_date"])
        text = (
            f"Ваша подписка активна до: {end_date.strftime('%d.%m.%Y')}\n"
            f"Тип подписки: {'Тестовый период' if sub['is_trial'] else 'Платная подписка'}"
        )
    
    await bot.send_message(user_id, text)

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Показывает статус подписки"""
    await show_subscription_status(message.from_user.id)

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("У вас нет доступа к админ-панели.")
        return
    
    text = "Админ-панель:"
    builder = InlineKeyboardBuilder()
    builder.button(text="Список активных подписок", callback_data="admin_subs")
    builder.button(text="Отключить подписку", callback_data="admin_deactivate")
    builder.button(text="Продлить подписку", callback_data="admin_extend")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())

async def check_expired_subscriptions():
    """Проверяет и отключает истекшие подписки"""
    while True:
        expired = await get_expired_subscriptions()
        for user_id, sub_type in expired:
            await deactivate_subscription(user_id)
            await bot.send_message(
                user_id,
                "⚠️ Ваша подписка истекла. Для продления выберите новый тариф."
            )
        await asyncio.sleep(3600)  # Проверка каждый час

async def main():
    """Запуск бота"""
    await init_db()
    
    # Запуск проверки истекших подписок
    asyncio.create_task(check_expired_subscriptions())
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 