from fastapi import FastAPI
from fastmcp import FastMCP

from stock_api import app as stock_api_app

def create_app() -> FastAPI:
    instructions = (
        "이 MCP 서버는 주식 매수/매도, 잔고 조회, 거래 내역 조회, 시세 조회 기능을 제공합니다."
    )

    # 1) 기존 FastAPI의 API 전체를 MCP 도구 세트로 래핑하고 MCP 서버 객체를 생성합니다.
    mcp = FastMCP.from_fastapi(
        stock_api_app,
        name="Stock Trading MCP",
        instructions=instructions,
    )

    # 2) FastAPI API에 정의되지 않은 이외 도구를 @mcp.tool로 추가 등록합니다.(즉 API가 아닌 파이썬 개별 함수)
	# 즉 1)에서 생성한 서버에 도구 추가
    @mcp.tool(
        name="get_price",
        description="특정 종목의 실시간 주가 또는 최근 종가를 반환합니다.",
    )
    async def get_price(ticker: str) -> dict:
        """FinanceDataReader로 가장 최근 종가를 가져와 반환"""
        import FinanceDataReader as fdr

        df = fdr.DataReader(ticker)
        latest = df.iloc[-1]
        return {
            "ticker": ticker,
            "date": latest.name.strftime("%Y-%m-%d"),
            "close": int(latest["Close"]),
        }

    # 3) MCP JSON‑RPC 서브 앱 생성 (StreamableHttp 사용)
    mcp_app = mcp.streamable_http_app(path="/")

    # 4) 루트 FastAPI에 REST와 MCP를 마운트
    root_app = FastAPI(
        title="Stock Trading Service with MCP",
        lifespan=mcp_app.lifespan,
    )

    root_app.mount("/api", stock_api_app)
    root_app.mount("/mcp", mcp_app)

    @root_app.get("/")
    async def root() -> dict:
        return {
            "message": "Stock Trading Service with MCP",
            "api": "/api",
            "mcp": "/mcp",
        }

    return root_app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("my_server:app", host="0.0.0.0", port=8888, reload=True)