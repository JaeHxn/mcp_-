# backend_api.py
# uvicorn backend_api:app --host 0.0.0.0 --port 9000     으로 실행.
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

# 가짜 주문 DB
FAKE_ORDERS: Dict[str, Dict] = {
    "ORDER123": {
        "order_id": "ORDER123",
        "status": "배송중",
        "courier": "CJ대한통운",
        "tracking_number": "1234-5678-0000",
        "last_update": "2025-11-13 09:00",
    },
    "ORDER999": {
        "order_id": "ORDER999",
        "status": "배송완료",
        "courier": "로젠택배",
        "tracking_number": "9999-8888-7777",
        "last_update": "2025-11-12 15:30",
    },
}

class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    courier: str
    tracking_number: str
    last_update: str

@app.get("/api/order/{order_id}", response_model=OrderStatusResponse)
async def get_order_status(order_id: str):
    if order_id not in FAKE_ORDERS:
        # 404 대신 간단히 에러 메시지 리턴해도 되고
        return OrderStatusResponse(
            order_id=order_id,
            status="주문을 찾을 수 없습니다",
            courier="-",
            tracking_number="-",
            last_update="-",
        )
    return OrderStatusResponse(**FAKE_ORDERS[order_id])
