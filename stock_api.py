import FinanceDataReader as fdr
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, Dict, List
from typing import Any
import sqlite3
from pathlib import Path
from contextlib import contextmanager

app = FastAPI(title="Stock Trading API", version="1.0.0")

# SQLite 데이터베이스 파일 경로
DB_FILE = Path(__file__).parent / "stock_trading.db"

# 간단한 비밀번호 설정
ACCOUNT_PASSWORD = "1234"

# DB 연결 관리
@contextmanager
def get_db():
    """SQLite 연결을 관리하는 컨텍스트 매니저"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # 딕셔너리처럼 접근 가능
    try:
        yield conn
    finally:
        conn.close()

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

    with get_db() as conn:
        cursor = conn.cursor()
        
        # 현재 잔고 확인
        cursor.execute("SELECT cash_balance FROM accounts WHERE account_id = 1")
        row = cursor.fetchone()
        cash_balance = row[0]
        
        if cost > cash_balance:
            raise HTTPException(status_code=400, detail=f"잔고가 부족합니다. 현재 잔고는 {cash_balance:,}원이며, 총 {cost:,}원이 필요합니다.")
        
        # 잔고 업데이트
        new_balance = cash_balance - int(cost)
        cursor.execute("UPDATE accounts SET cash_balance = ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = 1", (new_balance,))
        
        # 포트폴리오 확인 및 업데이트
        cursor.execute("SELECT qty, avg_price FROM portfolio WHERE account_id = 1 AND ticker = ?", (trade.ticker,))
        existing = cursor.fetchone()
        
        if existing:
            existing_qty, existing_avg = existing[0], existing[1]
            total_qty = existing_qty + trade.qty
            avg_price = ((existing_qty * existing_avg) + cost) / total_qty
            cursor.execute("""
                UPDATE portfolio 
                SET qty = ?, avg_price = ?, name = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE account_id = 1 AND ticker = ?
            """, (total_qty, int(round(avg_price)), name, trade.ticker))
        else:
            total_qty = trade.qty
            avg_price = price
            cursor.execute("""
                INSERT INTO portfolio (account_id, ticker, name, qty, avg_price)
                VALUES (1, ?, ?, ?, ?)
            """, (trade.ticker, name, trade.qty, int(round(price))))
        
        # 거래 내역 저장
        cursor.execute("""
            INSERT INTO trade_history (account_id, trade_type, ticker, name, qty, price, avg_price)
            VALUES (1, 'buy', ?, ?, ?, ?, ?)
        """, (trade.ticker, name, trade.qty, int(round(price)), int(round(avg_price))))
        
        conn.commit()

    return {
        "message": f"{name} {trade.qty}주 매수 완료 (시장가 {round(price, 2)}원)",
        "available_cash": new_balance
    }


@app.post("/sell", summary="종목 매도", operation_id="sell_stock", response_model=dict)
async def sell_stock(trade: TradeRequest):
    """보유 종목을 지정한 수량만큼 매도합니다.

    보유 수량이 부족하면 400 오류를 반환합니다. 매도 후 잔여 수량이 0이면 포트폴리오에서 삭제합니다.
    """
    price = get_market_price(trade.ticker)
    name = get_corp_name(trade.ticker)
    revenue = trade.qty * price
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 보유 수량 확인
        cursor.execute("SELECT qty, avg_price FROM portfolio WHERE account_id = 1 AND ticker = ?", (trade.ticker,))
        existing = cursor.fetchone()
        
        if not existing or existing[0] < trade.qty:
            current_qty = existing[0] if existing else 0
            raise HTTPException(status_code=400, detail=f"보유한 수량이 부족합니다. 현재 보유: {current_qty}주, 요청 수량: {trade.qty:,}주")
        
        current_qty, current_avg_price = existing[0], existing[1]
        new_qty = current_qty - trade.qty
        
        # 잔고 업데이트
        cursor.execute("UPDATE accounts SET cash_balance = cash_balance + ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = 1", (int(revenue),))
        
        # 포트폴리오 업데이트
        if new_qty == 0:
            cursor.execute("DELETE FROM portfolio WHERE account_id = 1 AND ticker = ?", (trade.ticker,))
        else:
            cursor.execute("""
                UPDATE portfolio 
                SET qty = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE account_id = 1 AND ticker = ?
            """, (new_qty, trade.ticker))
        
        # 거래 내역 저장
        cursor.execute("""
            INSERT INTO trade_history (account_id, trade_type, ticker, name, qty, price, avg_price)
            VALUES (1, 'sell', ?, ?, ?, ?, ?)
        """, (trade.ticker, name, trade.qty, int(round(price)), int(round(current_avg_price))))
        
        # 업데이트된 잔고 조회
        cursor.execute("SELECT cash_balance FROM accounts WHERE account_id = 1")
        new_balance = cursor.fetchone()[0]
        
        conn.commit()

    return {
        "message": f"{name} {trade.qty}주 매도 완료 (시장가 {round(price, 2)}원)",
        "available_cash": new_balance
    }


@app.get("/balance", summary="잔고 조회", operation_id="get_balance", response_model=BalanceResponse)
async def get_balance(password: str = Header(..., alias="X-Account-Password")):
    """현재 보유 현금과 포트폴리오를 반환합니다.

    요청 시 HTTP 헤더의 `X-Account-Password` 값을 통해 비밀번호를 전달받습니다.
    """
    if password != ACCOUNT_PASSWORD:
        raise HTTPException(status_code=401, detail="잘못된 비밀번호입니다.")

    with get_db() as conn:
        cursor = conn.cursor()
        
        # 현재 잔고 조회
        cursor.execute("SELECT cash_balance FROM accounts WHERE account_id = 1")
        cash_balance = cursor.fetchone()[0]
        
        # 포트폴리오 조회
        cursor.execute("SELECT ticker, name, qty, avg_price FROM portfolio WHERE account_id = 1")
        rows = cursor.fetchall()
        
        portfolio_dict = {}
        for row in rows:
            ticker, name, qty, avg_price = row
            portfolio_dict[ticker] = PortfolioItem(
                qty=qty,
                name=name,
                avg_price=avg_price
            )
    
    return {
        "available_cash": cash_balance,
        "portfolio": portfolio_dict
    }


@app.get("/trades", summary="거래 내역 조회", operation_id="get_trade_history", response_model=List[TradeHistoryItem])
async def get_trade_history(
    start_date: Optional[date] = Query(None, description="조회 시작일 (예: 2025-07-01)"),
    end_date: Optional[date] = Query(None, description="조회 종료일 (예: 2025-07-28)")
):
    """지정 기간 동안의 거래 내역을 반환합니다."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date는 end_date보다 이후일 수 없습니다.")

    with get_db() as conn:
        cursor = conn.cursor()
        
        query = "SELECT trade_type, ticker, name, qty, price, avg_price, trade_datetime FROM trade_history WHERE account_id = 1"
        params = []
        
        if start_date:
            query += " AND DATE(trade_datetime) >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND DATE(trade_datetime) <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY trade_datetime DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            result.append(TradeHistoryItem(
                type=row[0],
                ticker=row[1],
                name=row[2],
                qty=row[3],
                price=row[4],
                avg_price=row[5],
                datetime=row[6]
            ))
    
    return result


@app.get("/", summary="서비스 안내")
async def root() -> Dict[str, str]:
    return {"message": "Welcome to the Stock Trading API"}