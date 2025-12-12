"""
SQLite 데이터베이스 초기화 스크립트
stock_trading.db 파일과 필요한 테이블들을 생성합니다.
"""
import sqlite3
import sys
from pathlib import Path

DB_FILE = Path(__file__).parent / "stock_trading.db"

def init_database():
    """데이터베이스와 테이블 초기화"""
    try:
        print(f"SQLite 데이터베이스 생성 중: {DB_FILE}")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. accounts 테이블 생성
        print("accounts 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT DEFAULT 'main',
                cash_balance INTEGER NOT NULL DEFAULT 10000000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ accounts 테이블 생성 완료")
        
        # 2. portfolio 테이블 생성
        print("portfolio 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL DEFAULT 1,
                ticker TEXT NOT NULL,
                name TEXT,
                qty INTEGER NOT NULL,
                avg_price INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id),
                UNIQUE(account_id, ticker)
            )
        """)
        print("✓ portfolio 테이블 생성 완료")
        
        # 3. trade_history 테이블 생성
        print("trade_history 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL DEFAULT 1,
                trade_type TEXT NOT NULL CHECK(trade_type IN ('buy', 'sell')),
                ticker TEXT NOT NULL,
                name TEXT,
                qty INTEGER NOT NULL,
                price INTEGER NOT NULL,
                avg_price INTEGER,
                trade_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_datetime ON trade_history(trade_datetime)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON trade_history(ticker)")
        print("✓ trade_history 테이블 생성 완료")
        
        # 4. 기본 계좌 생성
        print("기본 계좌 생성 중...")
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE account_id = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO accounts (account_id, account_name, cash_balance) 
                VALUES (1, 'main', 10000000)
            """)
            print("✓ 기본 계좌 생성 완료 (초기 잔고: 10,000,000원)")
        else:
            print("✓ 기본 계좌 이미 존재함")
        
        conn.commit()
        
        # 5. 테이블 목록 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\n생성된 테이블 목록:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
        print(f"\n✅ 데이터베이스 초기화 완료!")
        print(f"📁 데이터베이스 파일: {DB_FILE.absolute()}")
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ SQLite 오류 발생: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
