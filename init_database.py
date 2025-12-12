"""
MySQL 데이터베이스 초기화 스크립트
stock_trading DB와 필요한 테이블들을 생성합니다.
"""
import pymysql
import sys

# MySQL 연결 설정
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",  # XAMPP 기본값
    "port": 3306,
    "charset": "utf8mb4"
}

def init_database():
    """데이터베이스와 테이블 초기화"""
    try:
        # 1. MySQL 서버에 연결 (DB 선택 없이)
        print("MySQL 서버에 연결 중...")
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 2. 데이터베이스 생성
        print("stock_trading 데이터베이스 생성 중...")
        cursor.execute("CREATE DATABASE IF NOT EXISTS stock_trading DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("✓ 데이터베이스 생성 완료")
        
        # 3. 데이터베이스 선택
        cursor.execute("USE stock_trading")
        
        # 4. accounts 테이블 생성
        print("accounts 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id INT PRIMARY KEY AUTO_INCREMENT,
                account_name VARCHAR(100) DEFAULT 'main',
                cash_balance BIGINT NOT NULL DEFAULT 10000000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        print("✓ accounts 테이블 생성 완료")
        
        # 5. portfolio 테이블 생성
        print("portfolio 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INT PRIMARY KEY AUTO_INCREMENT,
                account_id INT NOT NULL DEFAULT 1,
                ticker VARCHAR(20) NOT NULL,
                name VARCHAR(100),
                qty INT NOT NULL,
                avg_price INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_account_ticker (account_id, ticker),
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        """)
        print("✓ portfolio 테이블 생성 완료")
        
        # 6. trade_history 테이블 생성
        print("trade_history 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INT PRIMARY KEY AUTO_INCREMENT,
                account_id INT NOT NULL DEFAULT 1,
                trade_type ENUM('buy', 'sell') NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                name VARCHAR(100),
                qty INT NOT NULL,
                price INT NOT NULL,
                avg_price INT,
                trade_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id),
                INDEX idx_trade_datetime (trade_datetime),
                INDEX idx_ticker (ticker)
            )
        """)
        print("✓ trade_history 테이블 생성 완료")
        
        # 7. 기본 계좌 생성
        print("기본 계좌 생성 중...")
        cursor.execute("""
            INSERT INTO accounts (account_name, cash_balance) 
            VALUES ('main', 10000000)
            ON DUPLICATE KEY UPDATE account_name = account_name
        """)
        conn.commit()
        print("✓ 기본 계좌 생성 완료 (초기 잔고: 10,000,000원)")
        
        # 8. 테이블 목록 확인
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("\n생성된 테이블 목록:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ 데이터베이스 초기화 완료!")
        return True
        
    except pymysql.Error as e:
        print(f"\n❌ 오류 발생: {e}")
        print("\n다음을 확인하세요:")
        print("1. XAMPP Control Panel에서 MySQL이 실행 중인지 확인")
        print("2. MySQL root 비밀번호 확인 (init_database.py의 DB_CONFIG 수정)")
        return False
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
