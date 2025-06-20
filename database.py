import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class RSIDatabase:
    def __init__(self, db_path: str):
        """Инициализация базы данных"""
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Создание таблиц в базе данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица для RSI сигналов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rsi_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        signal_type TEXT NOT NULL,  -- 'overbought' или 'oversold'
                        rsi_value REAL NOT NULL,
                        price REAL NOT NULL,
                        timestamp DATETIME NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица для настроек пользователя
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id INTEGER PRIMARY KEY,
                        symbols TEXT NOT NULL,  -- JSON список символов
                        timeframe TEXT NOT NULL,
                        rsi_oversold INTEGER DEFAULT 30,
                        rsi_overbought INTEGER DEFAULT 70,
                        notifications_enabled BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Создаем индексы для быстрого поиска
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
                    ON rsi_signals(symbol, timeframe)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON rsi_signals(timestamp)
                ''')
                
                conn.commit()
                logger.info("База данных инициализирована")
                
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
            
    def add_signal(self, symbol: str, timeframe: str, signal_type: str, 
                   rsi_value: float, price: float, timestamp) -> bool:
        """Добавление нового сигнала"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Конвертируем timestamp в строку если нужно
                if hasattr(timestamp, 'strftime'):
                    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    timestamp_str = str(timestamp)
                
                cursor.execute('''
                    INSERT INTO rsi_signals 
                    (symbol, timeframe, signal_type, rsi_value, price, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, timeframe, signal_type, rsi_value, price, timestamp_str))
                
                conn.commit()
                logger.info(f"Добавлен сигнал: {symbol} {signal_type} RSI={rsi_value:.2f}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении сигнала: {str(e)}")
            return False
            
    def get_recent_signals(self, limit: int = 100) -> List[Dict]:
        """Получение последних сигналов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT symbol, timeframe, signal_type, rsi_value, price, timestamp
                    FROM rsi_signals
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                
                signals = []
                for row in rows:
                    signals.append({
                        'symbol': row[0],
                        'timeframe': row[1],
                        'signal_type': row[2],
                        'rsi_value': row[3],
                        'price': row[4],
                        'timestamp': row[5]
                    })
                
                return signals
                
        except Exception as e:
            logger.error(f"Ошибка при получении сигналов: {str(e)}")
            return []
            
    def get_signals_by_symbol(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Получение сигналов по символу"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT symbol, timeframe, signal_type, rsi_value, price, timestamp
                    FROM rsi_signals
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (symbol, limit))
                
                rows = cursor.fetchall()
                
                signals = []
                for row in rows:
                    signals.append({
                        'symbol': row[0],
                        'timeframe': row[1],
                        'signal_type': row[2],
                        'rsi_value': row[3],
                        'price': row[4],
                        'timestamp': row[5]
                    })
                
                return signals
                
        except Exception as e:
            logger.error(f"Ошибка при получении сигналов по символу: {str(e)}")
            return []
            
    def save_user_settings(self, symbols: List[str], timeframe: str, 
                          rsi_oversold: int = 30, rsi_overbought: int = 70) -> bool:
        """Сохранение пользовательских настроек"""
        try:
            import json
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                symbols_json = json.dumps(symbols)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO user_settings 
                    (id, symbols, timeframe, rsi_oversold, rsi_overbought)
                    VALUES (1, ?, ?, ?, ?)
                ''', (symbols_json, timeframe, rsi_oversold, rsi_overbought))
                
                conn.commit()
                logger.info("Настройки пользователя сохранены")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении настроек: {str(e)}")
            return False
            
    def get_user_settings(self) -> Optional[Dict]:
        """Получение пользовательских настроек"""
        try:
            import json
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT symbols, timeframe, rsi_oversold, rsi_overbought, notifications_enabled
                    FROM user_settings WHERE id = 1
                ''')
                
                row = cursor.fetchone()
                
                if row:
                    return {
                        'symbols': json.loads(row[0]),
                        'timeframe': row[1],
                        'rsi_oversold': row[2],
                        'rsi_overbought': row[3],
                        'notifications_enabled': bool(row[4])
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при получении настроек: {str(e)}")
            return None 