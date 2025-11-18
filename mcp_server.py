# mcp_server.py
import os
import requests
from typing import Dict

from mcp.server.fastmcp import FastMCP

BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:9000")

mcp = FastMCP("ShoppingMallMCP")


@mcp.tool()
def track_delivery(order_id: str) -> Dict:
    """
    주문번호(order_id)로 배송 상태를 조회하는 MCP 툴.
    내부적으로는 백엔드 API /api/order/{order_id}를 호출한다.
    """
    try:
        resp = requests.get(f"{BASE_URL}/api/order/{order_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"배송조회 API 호출 실패: {e}") from e


# HTTP(SSE)로도 쓸 수 있게 앱 노출 (원하면)
app = mcp.sse_app()

if __name__ == "__main__":
    # MCP 프로토콜용 stdio 서버
    mcp.run(transport="stdio")
