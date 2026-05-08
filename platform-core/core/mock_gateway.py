import uuid
import random
from typing import Optional

from core.config import settings
from core.models import PaymentResult


class MockCloudPaymentsGateway:
    """
    Подставной платёжный шлюз.
    Имитирует CloudPayments для тестирования без реальных ключей.
    """

    def __init__(self):
        self.transactions: dict[str, dict] = {}
        self.public_id = settings.CP_PUBLIC_ID

    async def auth(self, amount: float, currency: str, invoice_id: str,
                   description: str = "", email: Optional[str] = None) -> PaymentResult:
        """Имитация холдирования — всегда успешно."""
        txn_id = f"mock_{uuid.uuid4().hex[:12]}"
        
        self.transactions[txn_id] = {
            "amount": amount,
            "currency": currency,
            "invoice_id": invoice_id,
            "description": description,
            "status": "hold"
        }
        
        return PaymentResult(
            success=True,
            transaction_id=txn_id,
            message="[MOCK] Деньги заморожены"
        )

    async def capture(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Имитация списания — ВСЕГДА успешно."""
        if transaction_id in self.transactions:
            self.transactions[transaction_id]["status"] = "captured"
        return PaymentResult(
            success=True,
            transaction_id=transaction_id,
            message="[MOCK] Деньги списаны"
        )

    async def refund(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Имитация возврата — ВСЕГДА успешно."""
        if transaction_id in self.transactions:
            self.transactions[transaction_id]["status"] = "refunded"
        # Даже если транзакция не найдена — говорим что возврат выполнен
        return PaymentResult(
            success=True,
            transaction_id=transaction_id,
            message="[MOCK] Деньги возвращены"
        )