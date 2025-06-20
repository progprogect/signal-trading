import asyncio
import logging
import pandas as pd
from binance.client import Client
from datetime import datetime, timedelta
import pandas_ta as ta

logger = logging.getLogger(__name__)

class BinanceConnector:
    def __init__(self, config):
        """Инициализация подключения к Binance"""
        try:
            self.client = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
            self.config = config
            logger.info("Подключение к Binance установлено")
        except Exception as e:
            logger.error(f"Ошибка при подключении к Binance: {str(e)}")
            self.client = None
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close_connection()
            
    def _check_connection(self) -> bool:
        """Проверка подключения к Binance"""
        try:
            if self.client is None:
                logger.error("Клиент Binance не инициализирован")
                return False
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Ошибка при проверке подключения к Binance: {str(e)}")
            return False
            
    async def get_historical_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Получение исторических данных с RSI"""
        try:
            if not self._check_connection():
                return None
                
            # Проверяем параметры
            if not isinstance(symbol, str) or not isinstance(timeframe, str):
                logger.error("Неверный тип параметров")
                return None
                
            logger.info(f"Запрашиваем {limit} свечей для {symbol} на {timeframe}")
            
            # Получаем данные
            klines = self.client.get_historical_klines(
                symbol=symbol,
                interval=timeframe,
                limit=limit + 50  # Запрашиваем больше для расчета RSI
            )
            
            if not klines:
                logger.error(f"Не удалось получить данные для {symbol} на таймфрейме {timeframe}")
                return None
                
            # Преобразуем данные в DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignored'
            ])
                                             
            # Конвертируем типы данных
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_columns] = df[numeric_columns].astype(float)
            
            # Устанавливаем timestamp как индекс
            df.set_index('timestamp', inplace=True)
            
            # Вычисляем RSI
            df['rsi'] = ta.rsi(df['close'], length=self.config.RSI_PERIOD)
            
            # Удаляем строки с NaN значениями RSI
            df = df.dropna(subset=['rsi'])
            
            # Возвращаем только нужное количество свечей
            df = df.tail(limit)
            
            logger.info(f"Получено {len(df)} свечей для {symbol} с RSI")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при получении исторических данных: {str(e)}")
            return None
            
    async def get_current_price(self, symbol: str) -> float:
        """Получение текущей цены"""
        try:
            if not self._check_connection():
                return None
                
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении текущей цены: {str(e)}")
            return None
            
    def close(self):
        """Закрытие соединения"""
        try:
            if self.client:
                self.client.close_connection()
                logger.info("Соединение с Binance закрыто")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения: {str(e)}") 