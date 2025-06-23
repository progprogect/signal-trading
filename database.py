import sqlite3
import psycopg2
import psycopg2.extras
import logging
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class RSIDatabase:
    def __init__(self, db_url: str):
        """Инициализация базы данных (PostgreSQL или SQLite)"""
        self.db_url = db_url
        self.db_type = self._detect_db_type(db_url)
        self.init_database()
        
    def _detect_db_type(self, db_url: str) -> str:
        """Определение типа базы данных по URL"""
        if db_url.startswith('postgresql://') or db_url.startswith('postgres://'):
            return 'postgresql'
        else:
            return 'sqlite'
    
    def _get_connection(self):
        """Получение соединения с базой данных"""
        if self.db_type == 'postgresql':
            # Парсинг DATABASE_URL для PostgreSQL
            if self.db_url.startswith('postgres://'):
                # Railway использует postgres://, но psycopg2 требует postgresql://
                self.db_url = self.db_url.replace('postgres://', 'postgresql://', 1)
            return psycopg2.connect(self.db_url)
        else:
            # SQLite для локальной разработки
            db_path = self.db_url.replace('sqlite:///', '')
            return sqlite3.connect(db_path)
        
    def init_database(self):
        """Создание таблиц в базе данных"""
        try:
            conn = self._get_connection()
            
            if self.db_type == 'postgresql':
                cursor = conn.cursor()
                
                # Таблица для RSI сигналов (PostgreSQL)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rsi_signals (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        timeframe VARCHAR(10) NOT NULL,
                        signal_type VARCHAR(20) NOT NULL,
                        rsi_value REAL NOT NULL,
                        price REAL NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        previous_rsi REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица для настроек пользователя (PostgreSQL)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id INTEGER PRIMARY KEY,
                        symbols TEXT NOT NULL,
                        timeframe VARCHAR(10) NOT NULL,
                        rsi_oversold INTEGER DEFAULT 30,
                        rsi_overbought INTEGER DEFAULT 70,
                        notifications_enabled BOOLEAN DEFAULT TRUE
                    )
                ''')
                
                # Таблица для пользователей Telegram (PostgreSQL)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS telegram_users (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT UNIQUE NOT NULL,
                        username VARCHAR(100),
                        first_name VARCHAR(100),
                        last_name VARCHAR(100),
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        approved_at TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Создаем индексы для быстрого поиска (PostgreSQL)
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
                    ON rsi_signals(symbol, timeframe)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON rsi_signals(timestamp)
                ''')
                
            else:
                # SQLite для локальной разработки
                cursor = conn.cursor()
                
                # Таблица для RSI сигналов (SQLite)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rsi_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
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
                    pass
                
                # Таблица для настроек пользователя (SQLite)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id INTEGER PRIMARY KEY,
                        symbols TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        rsi_oversold INTEGER DEFAULT 30,
                        rsi_overbought INTEGER DEFAULT 70,
                        notifications_enabled BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Таблица для пользователей Telegram (SQLite)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS telegram_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        approved_at DATETIME,
                        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Создаем индексы для быстрого поиска (SQLite)
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
                    ON rsi_signals(symbol, timeframe)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON rsi_signals(timestamp)
                ''')
            
            conn.commit()
            conn.close()
            logger.info(f"База данных ({self.db_type}) инициализирована")
            
            # Создаем дефолтные настройки если их нет
            self._create_default_settings()
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
            
    def _create_default_settings(self):
        """Создание дефолтных настроек пользователя"""
        try:
            # Проверяем, есть ли уже настройки
            if self.get_user_settings() is None:
                # Создаем дефолтные настройки
                default_symbols = ["BTCUSDT", "DOGEUSDT", "PEPEUSDT", "SUIUSDT", "BIGTIMEUSDT", "ALTUSDT", "WLDUSDT"]
                self.save_user_settings(
                    symbols=default_symbols,
                    timeframe="5m",
                    rsi_oversold=30,
                    rsi_overbought=70
                )
                logger.info("Созданы дефолтные настройки пользователя")
        except Exception as e:
            logger.error(f"Ошибка при создании дефолтных настроек: {str(e)}")
            
    def add_signal(self, symbol: str, timeframe: str, signal_type: str, 
                   rsi_value: float, price: float, timestamp, previous_rsi: float = None) -> bool:
        """Добавление нового сигнала"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Конвертируем timestamp в строку если нужно
            if hasattr(timestamp, 'strftime'):
                timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            else:
                timestamp_str = str(timestamp)
            
            if self.db_type == 'postgresql':
                cursor.execute('''
                    INSERT INTO rsi_signals 
                    (symbol, timeframe, signal_type, rsi_value, price, timestamp, previous_rsi)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (symbol, timeframe, signal_type, rsi_value, price, timestamp_str, previous_rsi))
            else:
                cursor.execute('''
                    INSERT INTO rsi_signals 
                    (symbol, timeframe, signal_type, rsi_value, price, timestamp, previous_rsi)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, timeframe, signal_type, rsi_value, price, timestamp_str, previous_rsi))
            
            conn.commit()
            conn.close()
            logger.info(f"Добавлен сигнал: {symbol} {signal_type} RSI={previous_rsi:.2f}->{rsi_value:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении сигнала: {str(e)}")
            return False
            
    def get_recent_signals(self, symbol: str = None, timeframe: str = None, hours_back: float = None, limit: int = 100) -> List[Dict]:
        """Получение последних сигналов с опциональной фильтрацией"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Базовый SQL запрос
            sql_base = '''
                SELECT symbol, timeframe, signal_type, rsi_value, price, timestamp, previous_rsi
                FROM rsi_signals
            '''
            
            conditions = []
            params = []
            
            # Добавляем условия фильтрации
            if symbol:
                conditions.append("symbol = " + ("%s" if self.db_type == 'postgresql' else "?"))
                params.append(symbol)
                
            if timeframe:
                conditions.append("timeframe = " + ("%s" if self.db_type == 'postgresql' else "?"))
                params.append(timeframe)
                
            if hours_back is not None:
                if self.db_type == 'postgresql':
                    conditions.append("timestamp >= NOW() - INTERVAL '%s hours'")
                else:
                    conditions.append("timestamp >= datetime('now', '-' || ? || ' hours')")
                params.append(hours_back)
            
            # Формируем полный SQL запрос
            if conditions:
                sql_query = sql_base + " WHERE " + " AND ".join(conditions)
            else:
                sql_query = sql_base
                
            sql_query += " ORDER BY timestamp DESC"
            
            # Добавляем LIMIT
            if self.db_type == 'postgresql':
                sql_query += " LIMIT %s"
            else:
                sql_query += " LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql_query, params)
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
            
            conn.close()
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка при получении сигналов: {str(e)}")
            return []
            
    def get_signals_by_symbol(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Получение сигналов по символу"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if self.db_type == 'postgresql':
                cursor.execute('''
                    SELECT symbol, timeframe, signal_type, rsi_value, price, timestamp, previous_rsi
                    FROM rsi_signals
                    WHERE symbol = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                ''', (symbol, limit))
            else:
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
            
            conn.close()
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка при получении сигналов по символу: {str(e)}")
            return []
            
    def save_user_settings(self, symbols: List[str], timeframe: str, 
                          rsi_oversold: int = 30, rsi_overbought: int = 70) -> bool:
        """Сохранение пользовательских настроек"""
        try:
            import json
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            symbols_json = json.dumps(symbols)
            
            if self.db_type == 'postgresql':
                cursor.execute('''
                    INSERT INTO user_settings 
                    (id, symbols, timeframe, rsi_oversold, rsi_overbought)
                    VALUES (1, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                    symbols = EXCLUDED.symbols,
                    timeframe = EXCLUDED.timeframe,
                    rsi_oversold = EXCLUDED.rsi_oversold,
                    rsi_overbought = EXCLUDED.rsi_overbought
                ''', (symbols_json, timeframe, rsi_oversold, rsi_overbought))
            else:
                cursor.execute('''
                    INSERT OR REPLACE INTO user_settings 
                    (id, symbols, timeframe, rsi_oversold, rsi_overbought)
                    VALUES (1, ?, ?, ?, ?)
                ''', (symbols_json, timeframe, rsi_oversold, rsi_overbought))
            
            conn.commit()
            conn.close()
            logger.info("Настройки пользователя сохранены")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении настроек: {str(e)}")
            return False
            
    def get_user_settings(self) -> Optional[Dict]:
        """Получение пользовательских настроек"""
        try:
            import json
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if self.db_type == 'postgresql':
                cursor.execute('''
                    SELECT symbols, timeframe, rsi_oversold, rsi_overbought, notifications_enabled
                    FROM user_settings WHERE id = 1
                ''')
            else:
                cursor.execute('''
                    SELECT symbols, timeframe, rsi_oversold, rsi_overbought, notifications_enabled
                    FROM user_settings WHERE id = 1
                ''')
            
            row = cursor.fetchone()
            
            conn.close()
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if self.db_type == 'postgresql':
                cursor.execute('''
                    INSERT INTO telegram_users 
                    (user_id, username, first_name, last_name, last_activity)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_activity = CURRENT_TIMESTAMP
                ''', (user_id, username, first_name, last_name))
            else:
                cursor.execute('''
                    INSERT OR REPLACE INTO telegram_users 
                    (user_id, username, first_name, last_name, last_activity)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, username, first_name, last_name))
            
            conn.commit()
            conn.close()
            logger.info(f"Пользователь Telegram добавлен: {user_id} (@{username})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя Telegram: {str(e)}")
            return False
            
    def get_telegram_users(self) -> List[Dict]:
        """Получение всех пользователей Telegram"""
        try:
            conn = self._get_connection()
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
            
            conn.close()
            return users
            
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей Telegram: {str(e)}")
            return []
            
    def get_approved_telegram_users(self) -> List[Dict]:
        """Получение одобренных пользователей Telegram"""
        try:
            conn = self._get_connection()
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
            
            conn.close()
            return users
            
        except Exception as e:
            logger.error(f"Ошибка при получении одобренных пользователей: {str(e)}")
            return []
            
    def update_telegram_user_status(self, user_id: int, status: str) -> bool:
        """Обновление статуса пользователя Telegram"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if self.db_type == 'postgresql':
                if status == 'approved':
                    cursor.execute('''
                        UPDATE telegram_users 
                        SET status = %s, approved_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                    ''', (status, user_id))
                else:
                    cursor.execute('''
                        UPDATE telegram_users 
                        SET status = %s, approved_at = NULL
                        WHERE user_id = %s
                    ''', (status, user_id))
            else:
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
                conn.close()
                logger.info(f"Статус пользователя {user_id} обновлен на '{status}'")
                return True
            else:
                conn.close()
                logger.warning(f"Пользователь {user_id} не найден")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса пользователя: {str(e)}")
            return False
            
    def delete_telegram_user(self, user_id: int) -> bool:
        """Удаление пользователя Telegram"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if self.db_type == 'postgresql':
                cursor.execute('DELETE FROM telegram_users WHERE user_id = %s', (user_id,))
            else:
                cursor.execute('DELETE FROM telegram_users WHERE user_id = ?', (user_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                logger.info(f"Пользователь {user_id} удален")
                return True
            else:
                conn.close()
                logger.warning(f"Пользователь {user_id} не найден для удаления")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя: {str(e)}")
            return False
            
    def get_telegram_user_status(self, user_id: int) -> Optional[str]:
        """Получение статуса пользователя Telegram"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if self.db_type == 'postgresql':
                cursor.execute('SELECT status FROM telegram_users WHERE user_id = %s', (user_id,))
            else:
                cursor.execute('SELECT status FROM telegram_users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            return row[0] if row else None
            
        except Exception as e:
            logger.error(f"Ошибка при получении статуса пользователя: {str(e)}")
            return None