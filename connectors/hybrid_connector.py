import asyncio
import logging
import pandas as pd
from .kraken_connector import KrakenConnector
from .coingecko_connector import CoinGeckoConnector  
from .yahoo_connector import YahooConnector
from .binance_public_connector import BinancePublicConnector

logger = logging.getLogger(__name__)

class HybridConnector:
    def __init__(self, config):
        """Гибридный коннектор с несколькими источниками данных"""
        self.config = config
        self.kraken_connector = KrakenConnector(config)
        self.coingecko_connector = CoinGeckoConnector(config)
        self.yahoo_connector = YahooConnector(config)
        self.binance_connector = BinancePublicConnector(config)
        
        # Приоритет коннекторов для каждого символа
        self.priority_map = {
            'BTCUSDT': ['binance', 'kraken', 'yahoo', 'coingecko'],
            'DOGEUSDT': ['binance', 'kraken', 'yahoo', 'coingecko'], 
            'PEPEUSDT': ['binance', 'kraken', 'coingecko', 'yahoo'],
            'SUIUSDT': ['binance', 'coingecko', 'yahoo', 'kraken'],
            'BIGTIMEUSDT': ['binance', 'yahoo', 'coingecko'],
            'ALTUSDT': ['binance', 'yahoo', 'coingecko'],
            'WLDUSDT': ['binance', 'yahoo', 'coingecko']
        }
        
        logger.info("Гибридный коннектор инициализирован")
        
    async def get_historical_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Получение исторических данных из наилучшего источника"""
        try:
            connectors = {
                'kraken': self.kraken_connector,
                'coingecko': self.coingecko_connector,
                'yahoo': self.yahoo_connector,
                'binance': self.binance_connector
            }
            
            # Получаем приоритетный список коннекторов для символа
            priority_list = self.priority_map.get(symbol, ['binance', 'kraken', 'yahoo', 'coingecko'])
            
            logger.info(f"Попытка получить данные для {symbol} через: {priority_list}")
            
            for connector_name in priority_list:
                if connector_name not in connectors:
                    continue
                    
                try:
                    logger.info(f"Пробуем {connector_name} для {symbol}")
                    connector = connectors[connector_name]
                    
                    df = await connector.get_historical_data(symbol, timeframe, limit)
                    
                    if df is not None and len(df) > 0:
                        logger.info(f"✅ Успешно получены данные для {symbol} через {connector_name}")
                        return df
                    else:
                        logger.warning(f"❌ {connector_name} не вернул данных для {symbol}")
                        
                except Exception as e:
                    logger.warning(f"❌ Ошибка в {connector_name} для {symbol}: {str(e)}")
                    continue
                    
            logger.error(f"❌ Все коннекторы не смогли получить данные для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка в гибридном коннекторе для {symbol}: {str(e)}")
            return None
            
    async def get_current_price(self, symbol: str) -> float:
        """Получение текущей цены из наилучшего источника"""
        try:
            connectors = {
                'kraken': self.kraken_connector,
                'coingecko': self.coingecko_connector,
                'yahoo': self.yahoo_connector,
                'binance': self.binance_connector
            }
            
            priority_list = self.priority_map.get(symbol, ['binance', 'kraken', 'yahoo', 'coingecko'])
            
            for connector_name in priority_list:
                if connector_name not in connectors:
                    continue
                    
                try:
                    connector = connectors[connector_name]
                    price = await connector.get_current_price(symbol)
                    
                    if price is not None and price > 0:
                        logger.info(f"✅ Получена цена для {symbol} через {connector_name}: ${price}")
                        return price
                        
                except Exception as e:
                    logger.warning(f"❌ Ошибка получения цены в {connector_name} для {symbol}: {str(e)}")
                    continue
                    
            logger.error(f"❌ Все коннекторы не смогли получить цену для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения цены в гибридном коннекторе для {symbol}: {str(e)}")
            return None
            
    def close(self):
        """Закрытие всех коннекторов"""
        self.kraken_connector.close()
        self.coingecko_connector.close()
        self.yahoo_connector.close()
        self.binance_connector.close()
        logger.info("Гибридный коннектор закрыт") 