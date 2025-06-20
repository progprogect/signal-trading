import asyncio
import logging
import pandas as pd
import requests
from datetime import datetime, timedelta
import pandas_ta as ta
import time

logger = logging.getLogger(__name__)

class BinancePublicConnector:
    def __init__(self, config):
        """Инициализация подключения к публичному API Binance"""
        self.config = config
        self.base_url = "https://api.binance.com/api/v3"
        self.last_request_time = 0
        logger.info("Binance Public API коннектор инициализирован")
        
    def _rate_limit(self):
        """Ограничение частоты запросов"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        # Минимум 100ms между запросами
        if time_since_last_request < 0.1:
            time.sleep(0.1 - time_since_last_request)
            
        self.last_request_time = time.time()
        
    def _convert_timeframe(self, timeframe: str) -> str:
        """Конвертация таймфрейма в формат Binance"""
        timeframe_mapping = {
            '1m': '1m',
            '3m': '3m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '2h': '2h',
            '4h': '4h',
            '6h': '6h',
            '8h': '8h',
            '12h': '12h',
            '1d': '1d'
        }
        
        return timeframe_mapping.get(timeframe, '5m')
        
    async def get_historical_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Получение исторических данных с RSI"""
        try:
            # Применяем rate limiting
            self._rate_limit()
            
            # Конвертируем таймфрейм
            binance_timeframe = self._convert_timeframe(timeframe)
            
            logger.info(f"Запрашиваем данные для {symbol} на {binance_timeframe}")
            
            # Подготавливаем параметры запроса
            params = {
                'symbol': symbol,
                'interval': binance_timeframe,
                'limit': limit + 50  # Запрашиваем больше для расчета RSI
            }
            
            # Делаем запрос к публичному API Binance
            url = f"{self.base_url}/klines"
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Ошибка API Binance: {response.status_code}, {response.text}")
                return None
                
            data = response.json()
            
            if not data:
                logger.warning(f"Нет данных для {symbol}")
                return None
                
            # Создаем DataFrame
            df = pd.DataFrame(data, columns=[
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
            
            # Убираем строки с NaN
            df = df.dropna()
            
            if len(df) < 20:
                logger.warning(f"Недостаточно данных для {symbol}: {len(df)} строк")
                return None
                
            # Вычисляем RSI
            df['rsi'] = ta.rsi(df['close'], length=self.config.RSI_PERIOD)
            
            # Удаляем строки с NaN значениями RSI
            df = df.dropna(subset=['rsi'])
            
            # Возвращаем только нужное количество свечей
            df = df.tail(limit)
            
            logger.info(f"Получено {len(df)} свечей для {symbol} с RSI (последний RSI: {df['rsi'].iloc[-1]:.2f})")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных для {symbol}: {str(e)}")
            return None
            
    async def get_current_price(self, symbol: str) -> float:
        """Получение текущей цены"""
        try:
            # Применяем rate limiting
            self._rate_limit()
            
            url = f"{self.base_url}/ticker/price"
            params = {'symbol': symbol}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'price' in data:
                    return float(data['price'])
                    
            logger.warning(f"Не удалось получить цену для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении цены для {symbol}: {str(e)}")
            return None
            
    def close(self):
        """Заглушка для совместимости"""
        logger.info("Binance Public API коннектор закрыт")
        pass 