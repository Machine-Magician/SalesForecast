import uuid
import logging
import hashlib
import secrets

from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


from core.config import settings
from core.database import get_db, init_db
from core.models import (
    OrderDB, UserDB, ReviewDB, MessageDB,
    UserRegisterRequest, UserLoginRequest, UserResponse,
    OrderCreateRequest, OrderResponse,
    ReviewCreateRequest, ReviewResponse,
    MessageSendRequest, MessageResponse,
    PaymentResult
)
from core.mock_gateway import MockCloudPaymentsGateway

# ═══════════════════════════════
# ЛОГИРОВАНИЕ
# ═══════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("platform")

# ═══════════════════════════════
# ПРИЛОЖЕНИЕ
# ═══════════════════════════════

app = FastAPI(title=settings.APP_TITLE)

# Отдаём веб-интерфейс
app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/app")
@app.get("/app/")
async def web_app():
    """Главная страница веб-приложения."""
    return FileResponse("web/index.html")

gateway = MockCloudPaymentsGateway()


@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("База данных инициализирована")
    logger.info(f"Шлюз: MOCK (тестовый режим)")


@app.get("/")
async def root():
    return {"status": "ok", "gateway": "mock", "debug": settings.DEBUG}


@app.get("/health")
async def health():
    return {"healthy": True}

# ═══════════════════════════════
# АВТОРИЗАЦИЯ
# ═══════════════════════════════

def hash_password(password: str) -> str:
    """Простой хэш пароля."""
    return hashlib.sha256(password.encode()).hexdigest()


@app.post("/auth/register", response_model=UserResponse)
async def auth_register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Регистрация с логином и паролем."""
    # Проверяем, не занят ли логин
    existing = await db.execute(select(UserDB).where(UserDB.login == req.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Логин уже занят")

    user_id = uuid.uuid4().hex[:12]
    logger.info(f"Регистрация: {req.full_name}, логин: {req.login}, роль: {req.role}")

    user = UserDB(
        user_id=user_id,
        full_name=req.full_name,
        phone=req.phone,
        role=req.role,
        login=req.login,
        password_hash=hash_password(req.password),
        inn=req.inn,
        card_number=req.card_number,
        is_verified=0,
        is_blocked=0
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        role=user.role,
        rating=user.rating,
        is_verified=bool(user.is_verified),
        is_blocked=bool(user.is_blocked),
        block_reason=user.block_reason,
        created_at=user.created_at
    )


@app.post("/auth/login", response_model=UserResponse)
async def auth_login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Вход по логину и паролю."""
    result = await db.execute(select(UserDB).where(UserDB.login == req.login))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if user.password_hash != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if user.is_blocked:
        raise HTTPException(
            status_code=403,
            detail=f"Аккаунт заблокирован: {user.block_reason or 'Причина не указана'}"
        )

    logger.info(f"Вход: {user.login}, роль: {user.role}")

    return UserResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        role=user.role,
        rating=user.rating,
        is_verified=bool(user.is_verified),
        is_blocked=False,
        created_at=user.created_at
    )


@app.get("/auth/me", response_model=UserResponse)
async def auth_me(user_id: str, db: AsyncSession = Depends(get_db)):
    """Проверить данные пользователя по user_id."""
    result = await db.execute(select(UserDB).where(UserDB.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return UserResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        role=user.role,
        rating=user.rating,
        is_verified=bool(user.is_verified),
        is_blocked=bool(user.is_blocked),
        block_reason=user.block_reason,
        created_at=user.created_at
    )


# ═══════════════════════════════
# ПОЛЬЗОВАТЕЛИ
# ═══════════════════════════════




@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDB).where(UserDB.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return UserResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        role=user.role,
        rating=user.rating,
        is_verified=bool(user.is_verified),
        created_at=user.created_at
    )


@app.get("/users/{user_id}/stats")
async def get_user_stats(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDB).where(UserDB.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    completed_result = await db.execute(
        select(OrderDB).where(
            OrderDB.executor_id == user_id,
            OrderDB.status == "completed"
        )
    )
    completed_orders = completed_result.scalars().all()
    total_earned = sum(o.amount - o.commission for o in completed_orders)

    logger.info(f"Запрошена статистика исполнителя {user_id}")

    return {
        "user_id": user_id,
        "full_name": user.full_name,
        "rating": user.rating,
        "total_reviews": user.total_reviews,
        "completed_orders": len(completed_orders),
        "total_earned": round(total_earned, 2)
    }


# ═══════════════════════════════
# ЗАКАЗЫ
# ═══════════════════════════════

@app.post("/orders/create", response_model=OrderResponse)
async def create_order(req: OrderCreateRequest, db: AsyncSession = Depends(get_db)):
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    commission = round(req.amount * 0.10, 2)

    logger.info(f"Новый заказ: {order_id}, сумма: {req.amount}, комиссия: {commission}")

    order = OrderDB(
        order_id=order_id,
        customer_id=req.customer_id,
        description=req.description,
        amount=req.amount,
        commission=commission,
        status="created"
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    return OrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        description=order.description,
        amount=order.amount,
        commission=order.commission,
        status=order.status,
        created_at=order.created_at
    )


@app.post("/orders/{order_id}/pay", response_model=PaymentResult)
async def pay_order(order_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status != "created":
        raise HTTPException(status_code=400, detail="Заказ уже оплачен или отменён")

    payment_result = await gateway.auth(
        amount=order.amount,
        currency="RUB",
        invoice_id=order_id,
        description=order.description
    )

    if payment_result.success:
        order.status = "hold"
        order.transaction_id = payment_result.transaction_id
        await db.commit()
        logger.info(f"Холд: {order_id}, транзакция: {payment_result.transaction_id}")
    else:
        logger.error(f"Ошибка холда: {order_id}, {payment_result.message}")

    return payment_result


@app.post("/orders/{order_id}/accept", response_model=OrderResponse)
async def accept_order(order_id: str, executor_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status != "hold":
        raise HTTPException(status_code=400, detail="Заказ нельзя принять")

    order.executor_id = executor_id
    order.status = "in_progress"
    await db.commit()

    logger.info(f"Заказ {order_id} принят исполнителем {executor_id}")

    return OrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        executor_id=order.executor_id,
        description=order.description,
        amount=order.amount,
        commission=order.commission,
        status=order.status,
        transaction_id=order.transaction_id,
        created_at=order.created_at
    )


@app.post("/orders/{order_id}/ready")
async def order_ready(order_id: str, db: AsyncSession = Depends(get_db)):
    """Исполнитель сообщает о готовности."""
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    order.status = "ready"  # ← меняем статус на ready
    await db.commit()

    logger.info(f"Исполнитель сообщил о готовности: {order_id}")

    return {
        "order_id": order_id,
        "status": order.status,
        "message": "Заказчик уведомлён о готовности"
    }

@app.post("/orders/{order_id}/complete", response_model=PaymentResult)
async def complete_order(order_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status != "ready":
        raise HTTPException(status_code=400, detail="Исполнитель ещё не подтвердил готовность")

    payment_result = await gateway.capture(order.transaction_id)

    if payment_result.success:
        order.status = "completed"
        order.completed_at = datetime.utcnow()
        await db.commit()
        logger.info(f"Заказ {order_id} завершён, деньги списаны")
    else:
        logger.error(f"Ошибка списания: {order_id}, {payment_result.message}")

    return payment_result


@app.post("/orders/{order_id}/cancel", response_model=PaymentResult)
async def cancel_order(order_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status == "completed":
        raise HTTPException(status_code=400, detail="Нельзя отменить завершённый заказ")

    payment_result = await gateway.refund(order.transaction_id) if order.transaction_id else PaymentResult(success=True, message="Без транзакции")

    if payment_result.success:
        order.status = "cancelled"
        await db.commit()
        logger.info(f"Заказ {order_id} отменён, деньги возвращены")
    else:
        logger.error(f"Ошибка возврата: {order_id}, {payment_result.message}")

    return payment_result


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Проверяем, есть ли отзыв
    review_result = await db.execute(select(ReviewDB).where(ReviewDB.order_id == order_id))
    has_review = review_result.scalar_one_or_none() is not None

    return OrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        executor_id=order.executor_id,
        description=order.description,
        amount=order.amount,
        commission=order.commission,
        status=order.status,
        transaction_id=order.transaction_id,
        created_at=order.created_at,
        completed_at=order.completed_at,
        has_review=has_review  # ← добавили
    )


@app.get("/orders")
async def list_orders(
        skip: int = 0,
        limit: int = 100,
        filter: str = "all",  # "all" или "today"
        db: AsyncSession = Depends(get_db)
):
    """Список заказов с фильтрацией."""
    query = select(OrderDB).order_by(OrderDB.created_at.desc())

    if filter == "today":
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.where(OrderDB.created_at >= today_start)

    result = await db.execute(query.offset(skip).limit(limit))
    orders = result.scalars().all()

    # Собираем ответы с проверкой отзывов
    order_responses = []
    for o in orders:
        review_result = await db.execute(select(ReviewDB).where(ReviewDB.order_id == o.order_id))
        has_review = review_result.scalar_one_or_none() is not None

        order_responses.append(OrderResponse(
            order_id=o.order_id,
            customer_id=o.customer_id,
            executor_id=o.executor_id,
            description=o.description,
            amount=o.amount,
            commission=o.commission,
            status=o.status,
            transaction_id=o.transaction_id,
            created_at=o.created_at,
            completed_at=o.completed_at,
            has_review=has_review
        ))

    return {
        "count": len(order_responses),
        "orders": order_responses
    }

@app.post("/orders/{order_id}/rework")
async def rework_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Заказчик возвращает заказ на доработку."""
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status != "ready":
        raise HTTPException(status_code=400, detail="Заказ не в статусе готовности")

    order.status = "back_to_work"
    await db.commit()

    logger.info(f"Заказ {order_id} возвращён на доработку")

    return {"order_id": order_id, "status": order.status, "message": "Возвращён на доработку"}

# ═══════════════════════════════
# ОТЗЫВЫ И РЕЙТИНГ
# ═══════════════════════════════

@app.post("/reviews/create", response_model=ReviewResponse)
async def create_review(req: ReviewCreateRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrderDB).where(OrderDB.order_id == req.order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status != "completed":
        raise HTTPException(status_code=400, detail="Можно оценить только завершённый заказ")
    if order.customer_id != req.customer_id:
        raise HTTPException(status_code=403, detail="Только заказчик может оставить отзыв")

    existing = await db.execute(select(ReviewDB).where(ReviewDB.order_id == req.order_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Отзыв уже оставлен")

    review_id = f"REV-{uuid.uuid4().hex[:8].upper()}"

    review = ReviewDB(
        review_id=review_id,
        order_id=req.order_id,
        customer_id=req.customer_id,
        executor_id=order.executor_id,
        rating=req.rating,
        comment=req.comment
    )
    db.add(review)

    user_result = await db.execute(select(UserDB).where(UserDB.user_id == order.executor_id))
    executor = user_result.scalar_one_or_none()

    if executor:
        new_total = executor.total_reviews + 1
        new_rating = ((executor.rating * executor.total_reviews) + req.rating) / new_total
        executor.rating = round(new_rating, 2)
        executor.total_reviews = new_total

    await db.commit()
    await db.refresh(review)

    logger.info(f"Отзыв {review_id}: заказ {req.order_id}, оценка {req.rating}")

    return ReviewResponse(
        review_id=review.review_id,
        order_id=review.order_id,
        customer_name=req.customer_id,
        executor_name=order.executor_id or "",
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at
    )


@app.get("/reviews/{executor_id}")
async def get_reviews(executor_id: str, skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ReviewDB)
        .where(ReviewDB.executor_id == executor_id)
        .order_by(ReviewDB.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    reviews = result.scalars().all()

    return {
        "executor_id": executor_id,
        "count": len(reviews),
        "reviews": [
            ReviewResponse(
                review_id=r.review_id,
                order_id=r.order_id,
                customer_name=r.customer_id,
                executor_name=r.executor_id,
                rating=r.rating,
                comment=r.comment,
                created_at=r.created_at
            ) for r in reviews
        ]
    }

# ═══════════════════════════════
# ЧАТ
# ═══════════════════════════════

@app.post("/chat/send", response_model=MessageResponse)
async def send_message(req: MessageSendRequest, db: AsyncSession = Depends(get_db)):
    """Отправить сообщение в чат заказа."""
    order_result = await db.execute(select(OrderDB).where(OrderDB.order_id == req.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if req.sender_id not in (order.customer_id, order.executor_id):
        raise HTTPException(status_code=403, detail="Вы не участник этого заказа")

    message_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"

    message = MessageDB(
        message_id=message_id,
        order_id=req.order_id,
        sender_id=req.sender_id,
        sender_name=req.sender_name,
        text=req.text
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    logger.info(f"Сообщение {message_id} в заказе {req.order_id} от {req.sender_name}")

    return MessageResponse(
        message_id=message.message_id,
        order_id=message.order_id,
        sender_id=message.sender_id,
        sender_name=message.sender_name,
        text=message.text,
        created_at=message.created_at
    )


@app.get("/chat/{order_id}")
async def get_messages(order_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Получить сообщения по заказу."""
    result = await db.execute(
        select(MessageDB)
        .where(MessageDB.order_id == order_id)
        .order_by(MessageDB.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()

    return {
        "order_id": order_id,
        "count": len(messages),
        "messages": [
            MessageResponse(
                message_id=m.message_id,
                order_id=m.order_id,
                sender_id=m.sender_id,
                sender_name=m.sender_name,
                text=m.text,
                created_at=m.created_at
            ) for m in messages
        ]
    }





# ═══════════════════════════════
# ИНФОРМАЦИЯ
# ═══════════════════════════════

@app.get("/info/legal")
async def legal_info():
    return {
        "title": "Правовая информация",
        "laws": [
            {
                "name": "ФЗ-422 «О самозанятых»",
                "url": "http://www.consultant.ru/document/cons_doc_LAW_311977/",
                "description": "Закон о налоге на профессиональный доход"
            },
            {
                "name": "ФЗ-54 «О применении ККТ»",
                "url": "http://www.consultant.ru/document/cons_doc_LAW_42359/",
                "description": "Закон о контрольно-кассовой технике и чеках"
            },
            {
                "name": "ФЗ-115 «О противодействии отмыванию доходов»",
                "url": "http://www.consultant.ru/document/cons_doc_LAW_32834/",
                "description": "Финансовый мониторинг и безопасность"
            }
        ],
        "oferta": "Публичная оферта будет доступна после регистрации компании.",
        "checks": "Чеки формируются автоматически при каждом списании средств.",
        "commission": "Комиссия платформы составляет 10% от суммы заказа."
    }
