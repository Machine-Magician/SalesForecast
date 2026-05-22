from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from core.database import Base


# ═══════════════════════════════════════════
# МОДЕЛИ SQLALCHEMY (таблицы в БД)
# ═══════════════════════════════════════════

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    role = Column(String, nullable=False)
    inn = Column(String, nullable=True)
    card_number = Column(String, nullable=True)
    rating = Column(Float, default=5.0)
    total_reviews = Column(Integer, default=0)
    is_verified = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Новые поля для авторизации
    login = Column(String, unique=True, nullable=True)       # логин
    password_hash = Column(String, nullable=True)            # хэш пароля
    is_blocked = Column(Integer, default=0)                  # 0=активен, 1=заблокирован
    block_reason = Column(String, nullable=True)             # причина блокировки

    reviews_given = relationship("ReviewDB", foreign_keys="ReviewDB.customer_id", back_populates="customer")
    reviews_received = relationship("ReviewDB", foreign_keys="ReviewDB.executor_id", back_populates="executor")

class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, unique=True, nullable=False)
    customer_id = Column(String, nullable=False)  # user_id заказчика
    executor_id = Column(String, nullable=True)  # user_id исполнителя
    description = Column(Text, default="")
    amount = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)  # комиссия платформы
    status = Column(String, default="created")  # created/hold/in_progress/completed/cancelled/refunded
    transaction_id = Column(String, nullable=True)  # ID транзакции в платёжном шлюзе
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Связи
    review = relationship("ReviewDB", back_populates="order", uselist=False)


class ReviewDB(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String, unique=True, nullable=False)
    order_id = Column(String, ForeignKey("orders.order_id"), nullable=False)
    customer_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    executor_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    order = relationship("OrderDB", back_populates="review")
    customer = relationship("UserDB", foreign_keys=[customer_id], back_populates="reviews_given")
    executor = relationship("UserDB", foreign_keys=[executor_id], back_populates="reviews_received")

class MessageDB(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, unique=True, nullable=False)
    order_id = Column(String, ForeignKey("orders.order_id"), nullable=False)
    sender_id = Column(String, nullable=False)      # user_id отправителя
    sender_name = Column(String, nullable=False)     # имя отправителя
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ═══════════════════════════════════════════
# PYDANTIC-МОДЕЛИ (запросы/ответы API)
# ═══════════════════════════════════════════

class OrderStatus(str, Enum):
    CREATED = "created"
    HOLD = "hold"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    BACK_TO_WORK = "back_to_work"     # ← новый
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentResult(BaseModel):
    success: bool
    transaction_id: Optional[str] = None
    message: str = ""


# --- Пользователи ---

class UserRegisterRequest(BaseModel):
    full_name: str
    phone: str
    role: str
    login: str                  # ← добавили
    password: str               # ← добавили
    inn: Optional[str] = None
    card_number: Optional[str] = None


class UserLoginRequest(BaseModel):
    """Запрос на вход."""
    login: str
    password: str


class UserResponse(BaseModel):
    user_id: str
    full_name: str
    role: str
    rating: float
    is_verified: bool
    is_blocked: bool = False           # ← добавили
    block_reason: Optional[str] = None # ← добавили
    created_at: datetime


# --- Заказы ---

class OrderCreateRequest(BaseModel):
    customer_id: str
    description: str
    amount: float  # в рублях


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    executor_id: Optional[str] = None
    description: str
    amount: float
    commission: float
    status: str
    transaction_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    has_review: bool = False  # ← добавили


# --- Отзывы ---

class ReviewCreateRequest(BaseModel):
    order_id: str
    customer_id: str
    rating: int = Field(ge=1, le=5, description="Оценка от 1 до 5")
    comment: str = ""


class ReviewResponse(BaseModel):
    review_id: str
    order_id: str
    customer_name: str
    executor_name: str
    rating: int
    comment: str
    created_at: datetime

class MessageSendRequest(BaseModel):
    order_id: str
    sender_id: str
    sender_name: str
    text: str


class MessageResponse(BaseModel):
    message_id: str
    order_id: str
    sender_id: str
    sender_name: str
    text: str
    created_at: datetime

