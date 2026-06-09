import httpx
from typing import Optional
from core.config import settings
from core.models import PaymentResult
import logging
logger = logging.getLogger("platform")


class AlfaBankGateway:
    """Интеграция с интернет-эквайрингом Альфа-Банка."""

    # BASE_URL = "https://alfa.rbsuat.com/payment/rest"  # Тестовая среда
    BASE_URL = "https://payment.alfabank.ru/payment/rest"  # Продуктивная среда (потом)

    def __init__(self):
        self.user_name = settings.ALFA_USERNAME
        self.password = settings.ALFA_PASSWORD
        self.return_url = "https://ipartnyor.ru/app"

    async def _request(self, method: str, data: dict) -> dict:
        """Отправка запроса к API Альфа-Банка."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/{method}",
                data={**data, "userName": self.user_name, "password": self.password}
            )
            return resp.json()

    async def auth(self, amount: float, currency: str, invoice_id: str,
                   description: str = "", email: Optional[str] = None) -> PaymentResult:
        """Холдирование (registerPreAuth.do)."""
        data = {
            "orderNumber": invoice_id,
            "amount": int(amount * 100),  # В копейки
            "currency": "810",  # Код валюты RUB для Альфа-Банка
            "description": description[:99] if description else "",
            "returnUrl": self.return_url,
            "failUrl": self.return_url,
        }
        if email:
            data["jsonParams"] = f'{{"email":"{email}"}}'

        try:
            resp = await self._request("registerPreAuth.do", data)
            logger.info(f"Альфа ответ: {resp}")

            if resp.get("orderId") and not resp.get("errorCode"):
                return PaymentResult(
                    success=True,
                    transaction_id=resp.get("orderId", ""),
                    message=resp.get("formUrl", "")  # Передаём formUrl в message
                )
        except Exception as e:
            return PaymentResult(success=False, message=str(e))

    async def capture(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Списание (deposit.do)."""
        data = {"orderId": transaction_id, "amount": int(amount * 100) if amount else 0}
        try:
            resp = await self._request("deposit.do", data)
            if resp.get("errorCode") == "0":
                return PaymentResult(success=True, transaction_id=transaction_id, message="Списание успешно")
            return PaymentResult(success=False, message=resp.get("errorMessage", "Ошибка списания"))
        except Exception as e:
            return PaymentResult(success=False, message=str(e))

    async def refund(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Возврат (refund.do)."""
        data = {"orderId": transaction_id, "amount": int(amount * 100) if amount else 0}
        try:
            resp = await self._request("refund.do", data)
            if resp.get("errorCode") == "0":
                return PaymentResult(success=True, transaction_id=transaction_id, message="Возврат успешен")
            return PaymentResult(success=False, message=resp.get("errorMessage", "Ошибка возврата"))
        except Exception as e:
            return PaymentResult(success=False, message=str(e))

    async def cancel(self, transaction_id: str) -> PaymentResult:
        """Отмена холдирования (reverse.do)."""
        data = {"orderId": transaction_id}
        try:
            resp = await self._request("reverse.do", data)
            if resp.get("errorCode") == "0":
                return PaymentResult(success=True, transaction_id=transaction_id, message="Холдирование отменено")
            return PaymentResult(success=False, message=resp.get("errorMessage", "Ошибка отмены"))
        except Exception as e:
            return PaymentResult(success=False, message=str(e))

    async def get_status(self, transaction_id: str) -> dict:
        """Проверить статус заказа."""
        data = {"orderId": transaction_id}
        try:
            resp = await self._request("getOrderStatus.do", data)
            return resp
        except Exception as e:
            return {"error": str(e)}