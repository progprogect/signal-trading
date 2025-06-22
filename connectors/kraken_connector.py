import asyncio
import logging
import pandas as pd
import requests
from datetime import datetime, timedelta
import pandas_ta as ta
import time

logger = logging.getLogger(__name__)

class KrakenConnector:
    def __init__(self, config):
        """Инициализация подключения к публичному API Kraken"""
        self.config = config
        self.base_url = "https://api.kraken.com/0/public"
        self.last_request_time = 0
        logger.info("Kraken Public API коннектор инициализирован")
        
    def _convert_symbol_to_kraken(self, symbol: str) -> str:
        """Конвертация символа в формат Kraken"""
        # Маппинг символов в Kraken формат
        symbol_mapping = {
            'BTCUSDT': 'XXBTZUSD',
            'DOGEUSDT': 'DOGEUSD',
            'PEPEUSDT': 'PEPEUSD',  # Возможно поддерживается
            'SUIUSDT': 'SUIUSD',   # Возможно поддерживается
            # Эти монеты могут не поддерживаться Kraken:
            # 'BIGTIMEUSDT', 'ALTUSDT', 'WLDUSDT'
            # Для них будем использовать другие коннекторы
        }
        
        return symbol_mapping.get(symbol, None)
        
    def _rate_limit(self):
        """Ограничение частоты запросов"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        # Минимум 1 секунда между запросами
        if time_since_last_request < 1:
            time.sleep(1 - time_since_last_request)
            
        self.last_request_time = time.time()
        
    def _convert_timeframe(self, timeframe: str) -> int:
        """Конвертация таймфрейма в формат Kraken (в минутах)"""
        timeframe_mapping = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }
        
        return timeframe_mapping.get(timeframe, 5)
        
    async def get_historical_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Получение исторических данных с RSI"""
        try:
            # Конвертируем символ
            kraken_symbol = self._convert_symbol_to_kraken(symbol)
            
            if kraken_symbol is None:
                logger.warning(f"Символ {symbol} не поддерживается Kraken")
                return None
                
            # Применяем rate limiting
            self._rate_limit()
            
            # Конвертируем таймфрейм
            interval = self._convert_timeframe(timeframe)
            
            logger.info(f"Запрашиваем данные для {kraken_symbol} ({symbol}) на {interval}m")
            
            # Подготавливаем параметры запроса
            params = {
                'pair': kraken_symbol,
                'interval': interval,
                'since': int((datetime.now() - timedelta(days=30)).timestamp())
            }
            
            # Делаем запрос к публичному API Kraken
            url = f"{self.base_url}/OHLC"
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Ошибка API Kraken: {response.status_code}")
                return None
                
            data = response.json()
            
            if 'error' in data and data['error']:
                logger.error(f"Ошибка Kraken API: {data['error']}")
                return None
                
            if 'result' not in data or not data['result']:
                logger.warning(f"Нет данных для {symbol}")
                return None
                
            # Получаем данные свечей
            pair_data = None
            for key, value in data['result'].items():
                if isinstance(value, list) and key != 'last':
                    pair_data = value
                    break
                    
            if not pair_data:
                logger.warning(f"Нет данных свечей для {symbol}")
                return None
                
            # Создаем DataFrame
            df = pd.DataFrame(pair_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'
            ])
            
            # Конвертируем типы данных
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
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
            kraken_symbol = self._convert_symbol_to_kraken(symbol)
            
            if kraken_symbol is None:
                logger.warning(f"Символ {symbol} не поддерживается Kraken")
                return None
                
            # Применяем rate limiting
            self._rate_limit()
            
            url = f"{self.base_url}/Ticker"
            params = {'pair': kraken_symbol}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    for pair_name, pair_data in data['result'].items():
                        if 'c' in pair_data:  # 'c' - последняя цена
                            return float(pair_data['c'][0])
                            
            logger.warning(f"Не удалось получить цену для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении цены для {symbol}: {str(e)}")
            return None
            
    def close(self):
        """Заглушка для совместимости"""
        logger.info("Kraken Public API коннектор закрыт")
        pass 