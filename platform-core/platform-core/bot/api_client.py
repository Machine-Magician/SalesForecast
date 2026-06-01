import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://platform-core:8000")


class PlatformAPI:
    """Клиент для отправки запросов к нашему FastAPI."""

    def __init__(self):
        self.base_url = API_URL

    async def register_user(self, full_name: str, phone: str, role: str, inn: str = None, card_number: str = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/users/register", json={
                "full_name": full_name,
                "phone": phone,
                "role": role,
                "inn": inn,
                "card_number": card_number
            })
            return resp.json()

    async def get_user(self, user_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/users/{user_id}")
            return resp.json()

    async def get_user_stats(self, user_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/users/{user_id}/stats")
            return resp.json()

    async def create_order(self, customer_id: str, description: str, amount: float) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/orders/create", json={
                "customer_id": customer_id,
                "description": description,
                "amount": amount
            })
            return resp.json()

    async def pay_order(self, order_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/orders/{order_id}/pay")
            return resp.json()

    async def accept_order(self, order_id: str, executor_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/orders/{order_id}/accept",
                params={"executor_id": executor_id}
            )
            return resp.json()

    async def complete_order(self, order_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/orders/{order_id}/complete")
            return resp.json()

    async def cancel_order(self, order_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/orders/{order_id}/cancel")
            return resp.json()

    async def get_order(self, order_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/orders/{order_id}")
            return resp.json()

    async def list_orders(self, skip: int = 0, limit: int = 10) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/orders", params={"skip": skip, "limit": limit})
            return resp.json()

    async def create_review(self, order_id: str, customer_id: str, rating: int, comment: str = "") -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/reviews/create", json={
                "order_id": order_id,
                "customer_id": customer_id,
                "rating": rating,
                "comment": comment
            })
            return resp.json()

    async def get_reviews(self, executor_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/reviews/{executor_id}")
            return resp.json()

    async def legal_info(self) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/info/legal")
            return resp.json()
