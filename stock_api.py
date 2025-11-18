import FinanceDataReader as fdr
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, Dict, List
from typing import Any

app = FastAPI(title="Stock Trading API", version="1.0.0")

# 전역 상태 정의
cash_balance: int = 10_000_000 # 초기 현금 1천만 원
portfolio: Dict[str, Dict[str, int | str]] = {} # 종목별 보유 수량 및 평균 단가
trade_history: List[Dict[str, int | str]] = [] # 거래 내역

# 간단한 비밀번호 설정
ACCOUNT_PASSWORD = "1234"

class PortfolioItem(BaseModel):
    """보유 종목 정보"""

    qty: int = Field(..., description="보유 수량")
    name: Optional[str] = Field(None, description="종목명")
    avg_price: int = Field(..., description="평균 단가")

class TradeRequest(BaseModel):
    """매수/매도"""

    ticker: str = Field(..., description="종목 코드 (예: 035420)")
    qty: int = Field(..., gt=0, description="매수 또는 매도할 수량")


class BalanceResponse(BaseModel):
    """잔고 조회"""

    available_cash: int = Field(..., description="현금 잔고(원)")
    portfolio: Dict[str, Any] = Field(..., description="종목별 보유 내역")

class TradeHistoryItem(BaseModel):
    """거래 내역"""

    type: str = Field(..., description="거래 종류 (buy 또는 sell)")
    name: Optional[str] = Field(None, description="종목명")
    ticker: str = Field(..., description="종목 코드")
    qty: int = Field(..., description="거래 수량")
    price: int = Field(..., description="거래 체결 가격")
    avg_price: Optional[int] = Field(None, description="거래 후 평균 단가")
    datetime: str = Field(..., description="거래 시각 (YYYY-MM-DD HH:MM:SS)")

def get_market_price(ticker: str) -> int:
    """주어진 종목 코드의 가장 최근 종가를 조회합니다.

    Args:
        ticker: 종목 코드

    Returns:
        int: 최근 종가

    Raises:
        HTTPException: 종목 데이터가 없는 경우
    """
    df = fdr.DataReader(ticker)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"종목 {ticker}에 대한 시장 데이터를 찾을 수 없습니다.")
    return int(df['Close'].iloc[-1])


def get_corp_name(ticker: str) -> str:
    """종목 코드를 종목명으로 변환합니다. 못 찾으면 그대로 코드 반환."""
    krx = fdr.StockListing("KRX")
    match = krx.loc[krx['Code'] == ticker, 'Name']
    return match.values[0] if not match.empty else ticker


@app.post("/buy", summary="종목 매수", operation_id="buy_stock", response_model=dict)
async def buy_stock(trade: TradeRequest):
    """주어진 종목을 지정한 수량만큼 매수합니다.

    요청 본문으로 종목 코드와 수량을 받으며, 현재 잔고가 부족하면 400 오류를 반환합니다.
    """
    price = get_market_price(trade.ticker)
    name = get_corp_name(trade.ticker)
    cost = trade.qty * price

    # 잔고 확인 및 업데이트
    global cash_balance
    global portfolio
    if cost > cash_balance:
        raise HTTPException(status_code=400, detail=f"잔고가 부족합니다. 현재 잔고는 {cash_balance:,}원이며, 총 {cost:,}원이 필요합니다.")
    cash_balance -= int(cost)
    existing = portfolio.get(trade.ticker, {"qty": 0, "avg_price": 0.0, "name": name})
    total_qty = existing["qty"] + trade.qty
    avg_price = ((existing["qty"] * existing["avg_price"]) + cost) / total_qty
    portfolio[trade.ticker] = {
        "qty": total_qty,
        "name": name,
        "avg_price": int(round(avg_price, 2))
    }
    trade_history.append({
        "type": "buy",
        "name": name,
        "ticker": trade.ticker,
        "qty": trade.qty,
        "price": int(round(price, 2)),
        "avg_price": int(round(avg_price, 2)),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    current_cash = cash_balance

    return {
        "message": f"{name} {trade.qty}주 매수 완료 (시장가 {round(price, 2)}원)",
        "available_cash": current_cash
    }


@app.post("/sell", summary="종목 매도", operation_id="sell_stock", response_model=dict)
async def sell_stock(trade: TradeRequest):
    """보유 종목을 지정한 수량만큼 매도합니다.

    보유 수량이 부족하면 400 오류를 반환합니다. 매도 후 잔여 수량이 0이면 포트폴리오에서 삭제합니다.
    """
    global cash_balance
    global portfolio
    if trade.ticker not in portfolio or portfolio[trade.ticker]["qty"] < trade.qty:
        raise HTTPException(status_code=400, detail=f"보유한 수량이 부족합니다. 현재 보유: {portfolio.get(trade.ticker, {}).get('qty', 0)}주, 요청 수량: {trade.qty:,}주")

    price = get_market_price(trade.ticker)
    name = get_corp_name(trade.ticker)
    revenue = trade.qty * price
    current_qty = portfolio[trade.ticker]["qty"]
    current_avg_price = portfolio[trade.ticker]["avg_price"]
    new_qty = current_qty - trade.qty
    cash_balance += int(revenue)
    if new_qty == 0:
        del portfolio[trade.ticker]
    else:
        portfolio[trade.ticker]["qty"] = new_qty
        portfolio[trade.ticker]["avg_price"] = current_avg_price

    trade_history.append({
        "type": "sell",
        "name": name,
        "ticker": trade.ticker,
        "qty": trade.qty,
        "price": int(round(price, 2)),
        "avg_price": int(round(current_avg_price, 2)),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    current_cash = cash_balance

    return {
        "message": f"{name} {trade.qty}주 매도 완료 (시장가 {round(price, 2)}원)",
        "available_cash": current_cash
    }


@app.get("/balance", summary="잔고 조회", operation_id="get_balance", response_model=BalanceResponse)
async def get_balance(password: str = Header(..., alias="X-Account-Password")):
    """현재 보유 현금과 포트폴리오를 반환합니다.

    요청 시 HTTP 헤더의 `X-Account-Password` 값을 통해 비밀번호를 전달받습니다.
    """
    if password != ACCOUNT_PASSWORD:
        raise HTTPException(status_code=401, detail="잘못된 비밀번호입니다.")

    typed_portfolio = {ticker: PortfolioItem(**data) for ticker, data in portfolio.items()}
    return {
        "available_cash": cash_balance,
        "portfolio": typed_portfolio
    }


@app.get("/trades", summary="거래 내역 조회", operation_id="get_trade_history", response_model=List[TradeHistoryItem])
async def get_trade_history(
    start_date: Optional[date] = Query(None, description="조회 시작일 (예: 2025-07-01)"),
    end_date: Optional[date] = Query(None, description="조회 종료일 (예: 2025-07-28)")
):
    """지정 기간 동안의 거래 내역을 반환합니다."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date는 end_date보다 이후일 수 없습니다.")

    filtered: List[Dict] = []
    for trade in trade_history:
        trade_dt = datetime.strptime(trade["datetime"], "%Y-%m-%d %H:%M:%S")
        if start_date and trade_dt.date() < start_date:
            continue
        if end_date and trade_dt.date() > end_date:
            continue
        filtered.append(trade)
    return filtered


@app.get("/", summary="서비스 안내")
async def root() -> Dict[str, str]:
    return {"message": "Welcome to the Stock Trading API"}