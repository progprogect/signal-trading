import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from database import RSIDatabase

logger = logging.getLogger(__name__)

class RSIAnalyzer:
    def __init__(self, config, database: RSIDatabase):
        """Инициализация RSI анализатора"""
        self.config = config
        self.database = database
        self.previous_rsi_states = {}  # Хранение предыдущих состояний RSI
        
    def analyze_rsi_signals(self, symbol: str, timeframe: str, df: pd.DataFrame) -> List[Dict]:
        """Анализ RSI сигналов для символа с улучшенной логикой"""
        try:
            if df is None or len(df) < 5:
                return []
                
            signals = []
            
            # Проверяем последние 5 свечей на предмет пропущенных сигналов
            lookback_candles = min(5, len(df))
            
            for i in range(lookback_candles - 1, 0, -1):
                current_rsi = df['rsi'].iloc[-i]
                previous_rsi = df['rsi'].iloc[-i-1]
                current_price = df['close'].iloc[-i]
                current_time = df.index[-i]
                
                # Пропускаем NaN значения
                if pd.isna(current_rsi) or pd.isna(previous_rsi):
                    continue
                
                # Проверяем, был ли уже обработан этот момент времени
                if self._was_signal_processed(symbol, timeframe, current_time):
                    continue
                
                signal_type = None
                
                # Пересечение уровня перепроданности (30) сверху вниз (вход в зону)
                if (previous_rsi > self.config.RSI_OVERSOLD and 
                    current_rsi <= self.config.RSI_OVERSOLD):
                    signal_type = "oversold_enter"
                    
                # Пересечение уровня перекупленности (70) снизу вверх (вход в зону)
                elif (previous_rsi < self.config.RSI_OVERBOUGHT and 
                      current_rsi >= self.config.RSI_OVERBOUGHT):
                    signal_type = "overbought_enter"
                
                # Если обнаружено пересечение, создаем сигнал
                if signal_type:
                    signal = {
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'signal_type': signal_type,
                        'rsi_value': current_rsi,
                        'price': current_price,
                        'timestamp': current_time,
                        'previous_rsi': previous_rsi
                    }
                    
                    # Проверяем, не дублируется ли сигнал
                    if not self._is_duplicate_signal(signal):
                        signals.append(signal)
                        
                        # Сохраняем сигнал в базу данных
                        self.database.add_signal(
                            symbol=symbol,
                            timeframe=timeframe,
                            signal_type=signal_type,
                            rsi_value=current_rsi,
                            price=current_price,
                            timestamp=current_time,
                            previous_rsi=previous_rsi
                        )
                        
                        logger.info(f"RSI сигнал: {symbol} {timeframe} {signal_type} "
                                   f"RSI: {previous_rsi:.2f} -> {current_rsi:.2f}")
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка при анализе RSI для {symbol}: {str(e)}")
            return []
            
    def _was_signal_processed(self, symbol: str, timeframe: str, timestamp) -> bool:
        """Проверка, был ли уже обработан сигнал для этого момента времени"""
        try:
            # Проверяем последние сигналы из базы данных
            recent_signals = self.database.get_recent_signals(symbol, timeframe, hours_back=2)
            
            for signal in recent_signals:
                # Преобразуем timestamp в строку для сравнения
                signal_time = signal.get('timestamp', '')
                if isinstance(signal_time, str):
                    signal_time = pd.to_datetime(signal_time)
                
                current_time = pd.to_datetime(timestamp)
                
                # Считаем обработанным, если разница менее 1 минуты
                if abs((signal_time - current_time).total_seconds()) < 60:
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при проверке обработанных сигналов: {str(e)}")
            return False
            
    def _is_duplicate_signal(self, signal: Dict) -> bool:
        """Проверка на дублирование сигнала"""
        try:
            symbol = signal['symbol']
            timeframe = signal['timeframe']
            signal_type = signal['signal_type']
            
            # Проверяем последние сигналы за 10 минут
            recent_signals = self.database.get_recent_signals(symbol, timeframe, hours_back=0.17)  # 10 минут
            
            for recent_signal in recent_signals:
                if recent_signal.get('signal_type') == signal_type:
                    logger.debug(f"Найден дублирующий сигнал для {symbol} {signal_type}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при проверке дублирования сигнала: {str(e)}")
            return False
            
    def analyze_historical_rsi_signals(self, symbol: str, timeframe: str, df: pd.DataFrame, days_back: int = 2) -> List[Dict]:
        """Анализ исторических RSI сигналов за указанный период"""
        try:
            if df is None or len(df) < 2:
                return []
                
            signals = []
            
            # Фильтруем данные за последние N дней
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
            
            # Фильтруем DataFrame по времени
            historical_df = df[df.index >= start_time]
            
            if len(historical_df) < 2:
                logger.warning(f"Недостаточно исторических данных для {symbol}")
                return []
            
            logger.info(f"Анализируем исторические данные для {symbol} за {days_back} дней: {len(historical_df)} свечей")
            
            # Проходим по всем свечам и ищем пересечения RSI
            for i in range(1, len(historical_df)):
                current_row = historical_df.iloc[i]
                previous_row = historical_df.iloc[i-1]
                
                current_rsi = current_row['rsi']
                previous_rsi = previous_row['rsi']
                current_price = current_row['close']
                current_time = current_row.name
                
                # Пропускаем NaN значения
                if pd.isna(current_rsi) or pd.isna(previous_rsi):
                    continue
                
                signal_type = None
                
                # Пересечение уровня перепроданности (30) снизу вверх
                if (previous_rsi <= self.config.RSI_OVERSOLD and 
                    current_rsi > self.config.RSI_OVERSOLD):
                    signal_type = "oversold_exit"
                    
                # Пересечение уровня перекупленности (70) сверху вниз
                elif (previous_rsi >= self.config.RSI_OVERBOUGHT and 
                      current_rsi < self.config.RSI_OVERBOUGHT):
                    signal_type = "overbought_exit"
                    
                # Пересечение уровня перепроданности (30) сверху вниз
                elif (previous_rsi > self.config.RSI_OVERSOLD and 
                      current_rsi <= self.config.RSI_OVERSOLD):
                    signal_type = "oversold_enter"
                    
                # Пересечение уровня перекупленности (70) снизу вверх
                elif (previous_rsi < self.config.RSI_OVERBOUGHT and 
                      current_rsi >= self.config.RSI_OVERBOUGHT):
                    signal_type = "overbought_enter"
                
                # Если обнаружено пересечение, создаем сигнал
                if signal_type:
                    signal = {
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'signal_type': signal_type,
                        'rsi_value': current_rsi,
                        'price': current_price,
                        'timestamp': current_time,
                        'previous_rsi': previous_rsi,
                        'historical': True  # Помечаем как исторический
                    }
                    
                    signals.append(signal)
                    
                    logger.debug(f"Исторический RSI сигнал: {symbol} {timeframe} {signal_type} "
                               f"RSI: {previous_rsi:.2f} -> {current_rsi:.2f} в {current_time}")
            
            logger.info(f"Найдено {len(signals)} исторических сигналов для {symbol} за {days_back} дней")
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка при анализе исторических RSI для {symbol}: {str(e)}")
            return []
            
    def get_signal_description(self, signal: Dict) -> str:
        """Получение описания сигнала для уведомления"""
        try:
            # Только для входов в зоны - выходы не показываем
            if signal['signal_type'] not in ['oversold_enter', 'overbought_enter']:
                return ""
            
            # Простой формат: название монеты + RSI
            symbol_clean = signal['symbol'].replace('USDT', '')
            rsi_value = signal['rsi_value']
            
            return f"{symbol_clean} RSI: {rsi_value:.1f}"
            
        except Exception as e:
            logger.error(f"Ошибка при формировании описания сигнала: {str(e)}")
            return "Ошибка при формировании описания сигнала"
            
    def get_tradingview_url(self, symbol: str, timeframe: str) -> str:
        """Генерация URL для TradingView"""
        try:
            # Убираем USDT из символа для TradingView
            tv_symbol = symbol.replace('USDT', 'USD')
            
            # Конвертируем таймфрейм в формат TradingView
            tv_timeframe_map = {
                '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
                '1h': '60', '2h': '120', '4h': '240', '6h': '360', 
                '8h': '480', '12h': '720', '1d': 'D'
            }
            
            tv_timeframe = tv_timeframe_map.get(timeframe, '5')
            
            url = (f"https://www.tradingview.com/chart/?symbol=BINANCE:{tv_symbol}"
                   f"&interval={tv_timeframe}")
            
            return url
            
        except Exception as e:
            logger.error(f"Ошибка при генерации TradingView URL: {str(e)}")
            return "https://www.tradingview.com"
            
    def should_notify(self, signal: Dict) -> bool:
        """Определение, нужно ли отправлять уведомление"""
        try:
            # Проверяем настройки пользователя
            user_settings = self.database.get_user_settings()
            
            if not user_settings or not user_settings.get('notifications_enabled', True):
                return False
                
            # Уведомляем только о входах в зоны перекупленности и перепроданности
            notify_signals = ['oversold_enter', 'overbought_enter']
            
            is_notify = signal['signal_type'] in notify_signals
            
            if is_notify:
                logger.info(f"Отправляем уведомление для сигнала: {signal['symbol']} {signal['signal_type']}")
            
            return is_notify
            
        except Exception as e:
            logger.error(f"Ошибка при проверке необходимости уведомления: {str(e)}")
            return False 