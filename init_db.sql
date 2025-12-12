-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS stock_trading DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE stock_trading;

-- 계좌 정보 테이블 (현금 잔고)
CREATE TABLE IF NOT EXISTS accounts (
    account_id INT PRIMARY KEY AUTO_INCREMENT,
    account_name VARCHAR(100) DEFAULT 'main',
    cash_balance BIGINT NOT NULL DEFAULT 10000000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 포트폴리오 테이블 (보유 종목)
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
);

-- 거래 내역 테이블
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
);

-- 기본 계좌 생성 (초기 현금 1천만원)
INSERT INTO accounts (account_name, cash_balance) 
VALUES ('main', 10000000)
ON DUPLICATE KEY UPDATE account_name = account_name;
