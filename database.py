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
                        previous_rsi REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Добавляем поле previous_rsi если его нет
                try:
                    cursor.execute('ALTER TABLE rsi_signals ADD COLUMN previous_rsi REAL')
                except sqlite3.OperationalError:
                    # Поле уже существует
                    pass
                
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
                
                # Таблица для пользователей Telegram
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS telegram_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE NOT NULL,  -- Telegram user ID
                        username TEXT,  -- Telegram username
                        first_name TEXT,  -- Имя пользователя
                        last_name TEXT,  -- Фамилия пользователя
                        status TEXT DEFAULT 'pending',  -- pending, approved, blocked
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        approved_at DATETIME,
                        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
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
                   rsi_value: float, price: float, timestamp, previous_rsi: float = None) -> bool:
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
                    (symbol, timeframe, signal_type, rsi_value, price, timestamp, previous_rsi)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, timeframe, signal_type, rsi_value, price, timestamp_str, previous_rsi))
                
                conn.commit()
                logger.info(f"Добавлен сигнал: {symbol} {signal_type} RSI={previous_rsi:.2f}->{rsi_value:.2f}")
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
                    SELECT symbol, timeframe, signal_type, rsi_value, price, timestamp, previous_rsi
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
                        'timestamp': row[5],
                        'previous_rsi': row[6]
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
                    SELECT symbol, timeframe, signal_type, rsi_value, price, timestamp, previous_rsi
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
                        'timestamp': row[5],
                        'previous_rsi': row[6]
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
            
    def add_telegram_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Добавление нового пользователя Telegram"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO telegram_users 
                    (user_id, username, first_name, last_name, last_activity)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, username, first_name, last_name))
                
                conn.commit()
                logger.info(f"Пользователь Telegram добавлен: {user_id} (@{username})")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя Telegram: {str(e)}")
            return False
            
    def get_telegram_users(self) -> List[Dict]:
        """Получение всех пользователей Telegram"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, user_id, username, first_name, last_name, status, 
                           created_at, approved_at, last_activity
                    FROM telegram_users
                    ORDER BY created_at DESC
                ''')
                
                rows = cursor.fetchall()
                
                users = []
                for row in rows:
                    users.append({
                        'id': row[0],
                        'user_id': row[1],
                        'username': row[2],
                        'first_name': row[3],
                        'last_name': row[4],
                        'status': row[5],
                        'created_at': row[6],
                        'approved_at': row[7],
                        'last_activity': row[8]
                    })
                
                return users
                
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей Telegram: {str(e)}")
            return []
            
    def get_approved_telegram_users(self) -> List[Dict]:
        """Получение одобренных пользователей Telegram"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name
                    FROM telegram_users
                    WHERE status = 'approved'
                ''')
                
                rows = cursor.fetchall()
                
                users = []
                for row in rows:
                    users.append({
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    })
                
                return users
                
        except Exception as e:
            logger.error(f"Ошибка при получении одобренных пользователей: {str(e)}")
            return []
            
    def update_telegram_user_status(self, user_id: int, status: str) -> bool:
        """Обновление статуса пользователя Telegram"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                approved_at = 'CURRENT_TIMESTAMP' if status == 'approved' else None
                
                if status == 'approved':
                    cursor.execute('''
                        UPDATE telegram_users 
                        SET status = ?, approved_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    ''', (status, user_id))
                else:
                    cursor.execute('''
                        UPDATE telegram_users 
                        SET status = ?, approved_at = NULL
                        WHERE user_id = ?
                    ''', (status, user_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Статус пользователя {user_id} обновлен на '{status}'")
                    return True
                else:
                    logger.warning(f"Пользователь {user_id} не найден")
                    return False
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса пользователя: {str(e)}")
            return False
            
    def delete_telegram_user(self, user_id: int) -> bool:
        """Удаление пользователя Telegram"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM telegram_users WHERE user_id = ?', (user_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Пользователь {user_id} удален")
                    return True
                else:
                    logger.warning(f"Пользователь {user_id} не найден для удаления")
                    return False
                
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя: {str(e)}")
            return False
            
    def get_telegram_user_status(self, user_id: int) -> Optional[str]:
        """Получение статуса пользователя Telegram"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT status FROM telegram_users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Ошибка при получении статуса пользователя: {str(e)}")
            return None