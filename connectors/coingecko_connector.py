import asyncio
import logging
import pandas as pd
import requests
from datetime import datetime, timedelta
import pandas_ta as ta
import time

logger = logging.getLogger(__name__)

class CoinGeckoConnector:
    def __init__(self, config):
        """Инициализация подключения к CoinGecko API"""
        self.config = config
        self.base_url = "https://api.coingecko.com/api/v3"
        self.last_request_time = 0
        logger.info("CoinGecko коннектор инициализирован")
        
    def _convert_symbol_to_coingecko(self, symbol: str) -> str:
        """Конвертация символа в CoinGecko ID"""
        # Маппинг символов в CoinGecko IDs
        symbol_mapping = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum',
            'DOGEUSDT': 'dogecoin',
            'ADAUSDT': 'cardano',
            'SOLUSDT': 'solana',
            'XRPUSDT': 'ripple',
            'DOTUSDT': 'polkadot',
            'AVAXUSDT': 'avalanche-2',
            'MATICUSDT': 'matic-network',
            'PEPEUSDT': 'pepe',
            'SUIUSDT': 'sui'
        }
        
        return symbol_mapping.get(symbol, None)
        
    def _rate_limit(self):
        """Ограничение частоты запросов (бесплатный API: 10-50 запросов в минуту)"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        # Минимум 2 секунды между запросами
        if time_since_last_request < 2:
            time.sleep(2 - time_since_last_request)
            
        self.last_request_time = time.time()
        
    async def get_historical_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Получение исторических данных с RSI"""
        try:
            # Конвертируем символ
            coingecko_id = self._convert_symbol_to_coingecko(symbol)
            
            if coingecko_id is None:
                logger.warning(f"Символ {symbol} не поддерживается CoinGecko")
                return None
                
            logger.info(f"Запрашиваем данные для {coingecko_id} ({symbol})")
            
            # Применяем rate limiting
            self._rate_limit()
            
            # Определяем количество дней для получения данных
            if timeframe == '5m':
                days = 1  # CoinGecko дает 5-минутные данные только за последний день
                url = f"{self.base_url}/coins/{coingecko_id}/market_chart"
                params = {
                    'vs_currency': 'usd',
                    'days': days,
                    'interval': 'hourly'  # Используем часовые данные
                }
            else:
                days = 30
                url = f"{self.base_url}/coins/{coingecko_id}/market_chart"
                params = {
                    'vs_currency': 'usd',
                    'days': days,
                    'interval': 'daily'
                }
                
            # Делаем запрос
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Ошибка API CoinGecko: {response.status_code}")
                return None
                
            data = response.json()
            
            if 'prices' not in data or not data['prices']:
                logger.warning(f"Нет данных цен для {symbol}")
                return None
                
            # Создаем DataFrame из данных цен
            prices = data['prices']
            df = pd.DataFrame(prices, columns=['timestamp', 'close'])
            
            # Конвертируем timestamp в datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Добавляем необходимые колонки (для простоты используем close как все цены)
            df['open'] = df['close'].shift(1).fillna(df['close'])
            df['high'] = df['close'] * 1.01  # Примерное значение
            df['low'] = df['close'] * 0.99   # Примерное значение
            df['volume'] = 1000000  # Фиктивное значение объема
            
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
            coingecko_id = self._convert_symbol_to_coingecko(symbol)
            
            if coingecko_id is None:
                logger.warning(f"Символ {symbol} не поддерживается CoinGecko")
                return None
                
            # Применяем rate limiting
            self._rate_limit()
                
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': coingecko_id,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if coingecko_id in data and 'usd' in data[coingecko_id]:
                    return float(data[coingecko_id]['usd'])
                    
            logger.warning(f"Не удалось получить цену для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении цены для {symbol}: {str(e)}")
            return None
            
    def close(self):
        """Заглушка для совместимости"""
        logger.info("CoinGecko коннектор закрыт")
        pass 