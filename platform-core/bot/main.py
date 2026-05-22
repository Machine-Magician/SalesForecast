import os
import asyncio
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from bot.api_client import PlatformAPI

load_dotenv()

# ═══════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PROXY_URL = os.getenv("PROXY_URL", "")  # socks5://user:pass@host:port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# Создаём бота с прокси или без
if PROXY_URL:
    from aiogram.client.session.aiohttp import AiohttpSession
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(storage=MemoryStorage())
api = PlatformAPI()

# Храним user_id платформы для каждого telegram_id
users: dict[int, str] = {}


# ═══════════════════════════════
# СОСТОЯНИЯ ДЛЯ ДИАЛОГОВ
# ═══════════════════════════════

class CreateOrder(StatesGroup):
    waiting_description = State()
    waiting_amount = State()


class RegisterExecutor(StatesGroup):
    waiting_inn = State()
    waiting_card = State()


class ReviewOrder(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()


# ═══════════════════════════════
# КЛАВИАТУРЫ
# ═══════════════════════════════

def main_menu(role: str) -> ReplyKeyboardMarkup:
    """Главное меню в зависимости от роли."""
    if role == "customer":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📝 Создать заказ")],
                [KeyboardButton(text="📋 Мои заказы")],
                [KeyboardButton(text="ℹ️ Информация")],
            ],
            resize_keyboard=True
        )
    elif role == "executor":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔍 Доступные заказы")],
                [KeyboardButton(text="📋 Мои заказы")],
                [KeyboardButton(text="📊 Статистика")],
                [KeyboardButton(text="ℹ️ Информация")],
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 Я заказчик")],
                [KeyboardButton(text="🔧 Я исполнитель")],
            ],
            resize_keyboard=True
        )


# ═══════════════════════════════
# СТАРТ
# ═══════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветствие и выбор роли."""
    telegram_id = message.from_user.id

    if telegram_id in users:
        # Уже зарегистрирован — показываем меню
        user_data = await api.get_user(users[telegram_id])
        role = user_data.get("role", "")
        await message.answer(
            f"С возвращением, {user_data.get('full_name', 'друг')}!",
            reply_markup=main_menu(role)
        )
    else:
        await message.answer(
            "Добро пожаловать на платформу!\nВыберите вашу роль:",
            reply_markup=main_menu("new")
        )


# ═══════════════════════════════
# ВЫБОР РОЛИ
# ═══════════════════════════════

@dp.message(F.text == "👤 Я заказчик")
async def become_customer(message: types.Message):
    """Регистрация как заказчик."""
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name or "Заказчик"
    phone = f"tg_{telegram_id}"

    user_data = await api.register_user(
        full_name=full_name,
        phone=phone,
        role="customer"
    )
    users[telegram_id] = user_data["user_id"]
    
    await message.answer(
        f"✅ Вы зарегистрированы как заказчик!\nВаш ID: {user_data['user_id']}",
        reply_markup=main_menu("customer")
    )


@dp.message(F.text == "🔧 Я исполнитель")
async def become_executor(message: types.Message, state: FSMContext):
    """Начало регистрации исполнителя."""
    telegram_id = message.from_user.id
    
    await message.answer(
        "Для регистрации исполнителем нужен ИНН.\nВведите ваш ИНН (12 цифр):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(RegisterExecutor.waiting_inn)
    await state.update_data(telegram_id=telegram_id)


@dp.message(RegisterExecutor.waiting_inn)
async def executor_inn(message: types.Message, state: FSMContext):
    """Получаем ИНН, запрашиваем карту."""
    inn = message.text.strip()
    await state.update_data(inn=inn)
    
    await message.answer("Введите номер карты для выплат (16 цифр):")
    await state.set_state(RegisterExecutor.waiting_card)


@dp.message(RegisterExecutor.waiting_card)
async def executor_card(message: types.Message, state: FSMContext):
    """Получаем карту, регистрируем."""
    card_number = message.text.strip()
    data = await state.get_data()
    
    full_name = message.from_user.full_name or "Исполнитель"
    phone = f"tg_{data['telegram_id']}"
    
    user_data = await api.register_user(
        full_name=full_name,
        phone=phone,
        role="executor",
        inn=data["inn"],
        card_number=card_number
    )
    
    users[data["telegram_id"]] = user_data["user_id"]
    
    await message.answer(
        f"✅ Вы зарегистрированы как исполнитель!\n"
        f"Ваш ID: {user_data['user_id']}\n"
        f"ИНН: {data['inn']}\n"
        f"Карта: {card_number[:4]} **** **** {card_number[-4:]}",
        reply_markup=main_menu("executor")
    )
    await state.clear()


# ═══════════════════════════════
# ЗАКАЗЧИК: СОЗДАТЬ ЗАКАЗ
# ═══════════════════════════════

@dp.message(F.text == "📝 Создать заказ")
async def create_order_start(message: types.Message, state: FSMContext):
    """Начало создания заказа."""
    await message.answer("Опишите, что нужно сделать:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(CreateOrder.waiting_description)


@dp.message(CreateOrder.waiting_description)
async def create_order_description(message: types.Message, state: FSMContext):
    """Получаем описание, запрашиваем сумму."""
    await state.update_data(description=message.text)
    await message.answer("Введите сумму в рублях (например, 2000):")
    await state.set_state(CreateOrder.waiting_amount)


@dp.message(CreateOrder.waiting_amount)
async def create_order_amount(message: types.Message, state: FSMContext):
    """Создаём заказ."""
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("Введите число! Например: 2000")
        return

    data = await state.get_data()
    telegram_id = message.from_user.id
    customer_id = users.get(telegram_id)

    if not customer_id:
        await message.answer("Сначала зарегистрируйтесь: /start")
        await state.clear()
        return

    order_data = await api.create_order(
        customer_id=customer_id,
        description=data["description"],
        amount=amount
    )

    # Оплата (холд) — показываем заказ и предлагаем оплатить
    order_id = order_data["order_id"]
    
    await message.answer(
        f"📝 Заказ создан!\n"
        f"ID: {order_id}\n"
        f"Описание: {data['description']}\n"
        f"Сумма: {amount} ₽\n"
        f"Комиссия платформы: {order_data['commission']} ₽\n\n"
        f"Для оплаты нажмите кнопку ниже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{order_id}")]
        ])
    )
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu("customer"))


@dp.callback_query(F.data.startswith("pay_"))
async def pay_order_callback(callback: types.CallbackQuery):
    """Оплата заказа (холд)."""
    order_id = callback.data.replace("pay_", "")
    result = await api.pay_order(order_id)

    if result.get("success"):
        await callback.message.edit_text(
            f"✅ Заказ {order_id} оплачен!\nТранзакция: {result['transaction_id']}\nСтатус: деньги заморожены."
        )
    else:
        await callback.message.edit_text(f"❌ Ошибка оплаты: {result.get('message')}")

    await callback.answer()


# ═══════════════════════════════
# ИСПОЛНИТЕЛЬ: ДОСТУПНЫЕ ЗАКАЗЫ
# ═══════════════════════════════

@dp.message(F.text == "🔍 Доступные заказы")
async def available_orders(message: types.Message):
    """Показать заказы, которые можно взять."""
    result = await api.list_orders(limit=20)
    orders = result.get("orders", [])

    # Фильтруем: только те, что в статусе hold
    available = [o for o in orders if o["status"] == "hold"]

    if not available:
        await message.answer("Пока нет доступных заказов.", reply_markup=main_menu("executor"))
        return

    for order in available:
        await message.answer(
            f"📝 Заказ: {order['order_id']}\n"
            f"Описание: {order['description']}\n"
            f"Сумма: {order['amount']} ₽\n"
            f"Комиссия: {order['commission']} ₽\n"
            f"Вы заработаете: {order['amount'] - order['commission']} ₽",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✋ Взять заказ", callback_data=f"accept_{order['order_id']}")]
            ])
        )


@dp.callback_query(F.data.startswith("accept_"))
async def accept_order_callback(callback: types.CallbackQuery):
    """Исполнитель берёт заказ."""
    order_id = callback.data.replace("accept_", "")
    telegram_id = callback.from_user.id
    executor_id = users.get(telegram_id)

    if not executor_id:
        await callback.message.answer("Вы не зарегистрированы. /start")
        await callback.answer()
        return

    result = await api.accept_order(order_id, executor_id)

    if result.get("status") == "in_progress":
        await callback.message.edit_text(
            f"✅ Вы взяли заказ {order_id}!\n"
            f"Когда выполните — сообщите заказчику.",
        )
        await callback.message.answer(
            f"Заказ {order_id} в работе. Нажмите кнопку, когда выполните:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Я выполнил", callback_data=f"complete_{order_id}")]
            ])
        )
    else:
        await callback.message.edit_text(f"❌ Не удалось взять заказ.")

    await callback.answer()


@dp.callback_query(F.data.startswith("complete_"))
async def complete_order_executor(callback: types.CallbackQuery):
    """Исполнитель подтверждает выполнение."""
    order_id = callback.data.replace("complete_", "")

    await callback.message.edit_text(
        f"Заказ {order_id} отмечен как готовый.\nОжидайте подтверждения заказчика."
    )

    # Уведомляем заказчика (пока просто логируем)
    logger.info(f"Исполнитель готов по заказу {order_id}")
    
    await callback.answer("✅ Заказчик уведомлён!")


# ═══════════════════════════════
# ОБЩИЕ: МОИ ЗАКАЗЫ
# ═══════════════════════════════

@dp.message(F.text == "📋 Мои заказы")
async def my_orders(message: types.Message):
    """Показать заказы пользователя."""
    telegram_id = message.from_user.id
    user_id = users.get(telegram_id)

    if not user_id:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    user_data = await api.get_user(user_id)
    all_orders = await api.list_orders(limit=50)
    
    role = user_data.get("role", "")
    
    if role == "customer":
        my = [o for o in all_orders.get("orders", []) if o["customer_id"] == user_id]
    else:
        my = [o for o in all_orders.get("orders", []) if o["executor_id"] == user_id]

    if not my:
        await message.answer("У вас пока нет заказов.")
        return

    for order in my:
        status_emoji = {
            "created": "🆕",
            "hold": "💳",
            "in_progress": "🔧",
            "completed": "✅",
            "cancelled": "❌"
        }.get(order["status"], "❓")

        await message.answer(
            f"{status_emoji} {order['order_id']}\n"
            f"Описание: {order['description']}\n"
            f"Сумма: {order['amount']} ₽\n"
            f"Статус: {order['status']}"
        )

        if order["status"] == "completed" and role == "customer":
            # Предложить оценить
            await message.answer(
                "Хотите оценить исполнителя?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⭐ Оценить", callback_data=f"review_{order['order_id']}")]
                ])
            )


@dp.callback_query(F.data.startswith("review_"))
async def review_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало оценки."""
    order_id = callback.data.replace("review_", "")
    await state.update_data(order_id=order_id)
    await callback.message.answer("Поставьте оценку от 1 до 5:")
    await state.set_state(ReviewOrder.waiting_rating)
    await callback.answer()


@dp.message(ReviewOrder.waiting_rating)
async def review_rating(message: types.Message, state: FSMContext):
    """Получаем оценку, запрашиваем комментарий."""
    try:
        rating = int(message.text)
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 5!")
        return

    await state.update_data(rating=rating)
    await message.answer("Напишите комментарий (или отправьте `-` чтобы пропустить):")
    await state.set_state(ReviewOrder.waiting_comment)


@dp.message(ReviewOrder.waiting_comment)
async def review_comment(message: types.Message, state: FSMContext):
    """Сохраняем отзыв."""
    comment = message.text if message.text != "-" else ""
    data = await state.get_data()
    telegram_id = message.from_user.id
    customer_id = users.get(telegram_id)

    result = await api.create_review(
        order_id=data["order_id"],
        customer_id=customer_id,
        rating=data["rating"],
        comment=comment
    )

    await message.answer(f"⭐ Спасибо за оценку {data['rating']}/5!")
    await state.clear()


# ═══════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════

@dp.message(F.text == "📊 Статистика")
async def stats(message: types.Message):
    """Статистика исполнителя."""
    telegram_id = message.from_user.id
    user_id = users.get(telegram_id)

    if not user_id:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return

    result = await api.get_user_stats(user_id)

    await message.answer(
        f"📊 Статистика\n\n"
        f"Имя: {result.get('full_name')}\n"
        f"Рейтинг: {'⭐' * int(result.get('rating', 0))} ({result.get('rating')})\n"
        f"Всего отзывов: {result.get('total_reviews')}\n"
        f"Выполнено заказов: {result.get('completed_orders')}\n"
        f"Заработано: {result.get('total_earned')} ₽"
    )


# ═══════════════════════════════
# ИНФОРМАЦИЯ
# ═══════════════════════════════

@dp.message(F.text == "ℹ️ Информация")
async def info(message: types.Message):
    """Правовая информация."""
    result = await api.legal_info()

    laws_text = "\n".join([
        f"• {law['name']}: {law['description']}"
        for law in result.get("laws", [])
    ])

    await message.answer(
        f"ℹ️ {result.get('title')}\n\n"
        f"📜 Законы:\n{laws_text}\n\n"
        f"💰 Комиссия: {result.get('commission')}\n"
        f"🧾 Чеки: {result.get('checks')}"
    )


# ═══════════════════════════════
# ЗАПУСК
# ═══════════════════════════════

async def main():
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
