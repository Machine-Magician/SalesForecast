from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
import httpx
from core.config import settings
from core.models import PaymentResult
from core.alfa_gateway import AlfaBankGateway


class GatewayName(str, Enum):
    """Список поддерживаемых платёжных шлюзов."""
    CLOUDPAYMENTS = "cloudpayments"
    YOOKASSA = "yookassa"


# ═══════════════════════════════════════════
# АБСТРАКТНЫЙ КЛАСС
# ═══════════════════════════════════════════

class BasePaymentGateway(ABC):
    """Шаблон для всех платёжных шлюзов."""

    @abstractmethod
    async def auth(self, amount: float, currency: str, invoice_id: str, 
                   description: str = "", email: Optional[str] = None) -> PaymentResult:
        """Авторизация (холдирование) — заблокировать деньги на карте."""
        ...

    @abstractmethod
    async def capture(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Подтверждение — списать замороженные деньги."""
        ...

    @abstractmethod
    async def refund(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Возврат — вернуть деньги."""
        ...


# ═══════════════════════════════════════════
# РЕАЛЬНАЯ РЕАЛИЗАЦИЯ CLOUDPAYMENTS
# ═══════════════════════════════════════════

class CloudPaymentsGateway(BasePaymentGateway):
    """Работа с API CloudPayments."""
    
    BASE_URL = "https://api.cloudpayments.ru"

    def __init__(self):
        self.public_id = settings.CP_PUBLIC_ID
        self.api_secret = settings.CP_API_SECRET
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Ленивое создание HTTP-клиента."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                auth=(self.public_id, self.api_secret),
                timeout=30.0
            )
        return self._client

    async def auth(self, amount: float, currency: str, invoice_id: str,
                   description: str = "", email: Optional[str] = None) -> PaymentResult:
        """
        Двухстадийный платёж (холдирование).
        Деньги блокируются на карте, но не списываются.
        """
        client = await self._get_client()
        
        data = {
            "Amount": amount,
            "Currency": currency,
            "InvoiceId": invoice_id,
            "Description": description,
        }
        if email:
            data["Email"] = email

        try:
            response = await client.post("/payments/cards/auth", json=data)
            response_data = response.json()
            
            if response_data.get("Success"):
                model = response_data.get("Model", {})
                return PaymentResult(
                    success=True,
                    transaction_id=str(model.get("TransactionId", "")),
                    message="Деньги заморожены"
                )
            else:
                return PaymentResult(
                    success=False,
                    message=response_data.get("Message", "Ошибка авторизации")
                )
        except Exception as e:
            return PaymentResult(success=False, message=str(e))

    async def capture(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Подтверждение платежа — списание замороженных денег."""
        client = await self._get_client()
        
        data = {"TransactionId": transaction_id}
        if amount is not None:
            data["Amount"] = amount

        try:
            response = await client.post("/payments/confirm", json=data)
            response_data = response.json()
            
            if response_data.get("Success"):
                return PaymentResult(
                    success=True,
                    transaction_id=transaction_id,
                    message="Деньги списаны"
                )
            else:
                return PaymentResult(
                    success=False,
                    message=response_data.get("Message", "Ошибка подтверждения")
                )
        except Exception as e:
            return PaymentResult(success=False, message=str(e))

    async def refund(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Возврат денег."""
        client = await self._get_client()
        
        data = {"TransactionId": transaction_id}
        if amount is not None:
            data["Amount"] = amount

        try:
            response = await client.post("/payments/refund", json=data)
            response_data = response.json()
            
            if response_data.get("Success"):
                return PaymentResult(
                    success=True,
                    transaction_id=transaction_id,
                    message="Деньги возвращены"
                )
            else:
                return PaymentResult(
                    success=False,
                    message=response_data.get("Message", "Ошибка возврата")
                )
        except Exception as e:
            return PaymentResult(success=False, message=str(e))

    async def close(self):
        """Закрыть HTTP-клиент."""
        if self._client:
            await self._client.aclose()
            self._client = None


# ═══════════════════════════════════════════
# ЗАГЛУШКА YOOKASSA (на будущее)
# ═══════════════════════════════════════════

class YooKassaGateway(BasePaymentGateway):
    """Заглушка. Будет реализована позже."""
    
    async def auth(self, amount: float, currency: str, invoice_id: str,
                   description: str = "", email: Optional[str] = None) -> PaymentResult:
        return PaymentResult(success=False, message="YooKassa пока не подключена")

    async def capture(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        return PaymentResult(success=False, message="YooKassa пока не подключена")

    async def refund(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        return PaymentResult(success=False, message="YooKassa пока не подключена")


# ═══════════════════════════════════════════
# ФАБРИКА: выбирает шлюз по настройке
# ═══════════════════════════════════════════



def get_gateway():
    if settings.GATEWAY == "alfabank":
        return AlfaBankGateway()
    elif settings.GATEWAY == "cloudpayments":
        return CloudPaymentsGateway()
    elif settings.GATEWAY == "yookassa":
        return YooKassaGateway()
    else:
        raise ValueError(f"Неизвестный шлюз: {settings.GATEWAY}")
