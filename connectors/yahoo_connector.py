import asyncio
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pandas_ta as ta

logger = logging.getLogger(__name__)

class YahooConnector:
    def __init__(self, config):
        """Инициализация подключения к Yahoo Finance"""
        self.config = config
        logger.info("Yahoo Finance коннектор инициализирован")
        
    def _convert_symbol_to_yahoo(self, symbol: str) -> str:
        """Конвертация символа Binance в формат Yahoo Finance"""
        # Маппинг криптовалют для Yahoo Finance (только проверенные символы)
        symbol_mapping = {
            'BTCUSDT': 'BTC-USD',
            'DOGEUSDT': 'DOGE-USD',
            'PEPEUSDT': 'PEPE-USD',
            'SUIUSDT': 'SUI-USD',
            # Новые символы - возможно поддерживаются
            'BIGTIMEUSDT': 'BIGTIME-USD',
            'ALTUSDT': 'ALT-USD', 
            'WLDUSDT': 'WLD-USD'
        }
        
        return symbol_mapping.get(symbol, None)  # Возвращаем None если символ не найден
        
    def _convert_timeframe_to_yahoo(self, timeframe: str) -> str:
        """Конвертация таймфрейма в формат Yahoo Finance"""
        timeframe_mapping = {
            '1m': '1m',
            '3m': '5m',  # Yahoo не поддерживает 3m, используем 5m
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
        
    def _get_period_for_timeframe(self, timeframe: str, limit: int) -> str:
        """Определение периода для получения данных"""
        if timeframe in ['1m', '5m']:
            return '7d'  # Максимум 7 дней для минутных данных
        elif timeframe in ['15m', '30m']:
            return '60d'  # 60 дней для получения достаточного количества данных
        elif timeframe in ['1h', '2h', '4h']:
            return '730d'  # 2 года для часовых данных
        else:
            return 'max'  # Максимальный период для дневных данных
            
    async def get_historical_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Получение исторических данных с RSI"""
        try:
            # Конвертируем символ и таймфрейм
            yahoo_symbol = self._convert_symbol_to_yahoo(symbol)
            yahoo_timeframe = self._convert_timeframe_to_yahoo(timeframe)
            period = self._get_period_for_timeframe(timeframe, limit)
            
            logger.info(f"Запрашиваем данные для {yahoo_symbol} на {yahoo_timeframe}")
            
            # Создаем тикер
            ticker = yf.Ticker(yahoo_symbol)
            
            # Получаем исторические данные
            df = ticker.history(
                period=period,
                interval=yahoo_timeframe,
                auto_adjust=True,
                prepost=False
            )
            
            if df.empty:
                logger.warning(f"Нет данных для {yahoo_symbol}")
                return None
                
            # Переименовываем колонки для совместимости
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high', 
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Убеждаемся, что у нас есть нужные колонки
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    logger.error(f"Отсутствует колонка {col} для {symbol}")
                    return None
            
            # Убираем строки с NaN
            df = df.dropna()
            
            if len(df) < 20:  # Минимум для RSI
                logger.warning(f"Недостаточно данных для {symbol}: {len(df)} строк")
                return None
                
            # Вычисляем RSI
            df['rsi'] = ta.rsi(df['close'], length=self.config.RSI_PERIOD)
            
            # Удаляем строки с NaN значениями RSI
            df = df.dropna(subset=['rsi'])
            
            # Возвращаем только нужное количество свечей
            df = df.tail(limit)
            
            logger.info(f"Получено {len(df)} свечей для {symbol} с RSI")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных для {symbol}: {str(e)}")
            return None
            
    async def get_current_price(self, symbol: str) -> float:
        """Получение текущей цены"""
        try:
            yahoo_symbol = self._convert_symbol_to_yahoo(symbol)
            ticker = yf.Ticker(yahoo_symbol)
            
            # Получаем последнюю цену
            info = ticker.info
            current_price = info.get('regularMarketPrice') or info.get('previousClose')
            
            if current_price:
                return float(current_price)
                
            # Альтернативный способ - через быстрые данные
            fast_info = ticker.fast_info
            if hasattr(fast_info, 'last_price'):
                return float(fast_info.last_price)
                
            logger.warning(f"Не удалось получить цену для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении цены для {symbol}: {str(e)}")
            return None
            
    def close(self):
        """Заглушка для совместимости"""
        logger.info("Yahoo Finance коннектор закрыт")
        pass 