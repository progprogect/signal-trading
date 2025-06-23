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
        """Анализ RSI сигналов для символа с проверкой только последней свечи"""
        try:
            if df is None or len(df) < 2:
                return []
                
            signals = []
            
            # Проверяем только последние две свечи для определения пересечения
            current_rsi = df['rsi'].iloc[-1]
            previous_rsi = df['rsi'].iloc[-2]
            current_price = df['close'].iloc[-1]
            current_time = df.index[-1]
            
            # Пропускаем NaN значения
            if pd.isna(current_rsi) or pd.isna(previous_rsi):
                return []
            

            
            signal_type = None
            
            # Все возможные пересечения RSI границ
            # Пересечение уровня перепроданности (30) сверху вниз (вход в зону)
            if (previous_rsi > self.config.RSI_OVERSOLD and 
                current_rsi <= self.config.RSI_OVERSOLD):
                signal_type = "oversold_enter"
                
            # Пересечение уровня перепроданности (30) снизу вверх (выход из зоны)
            elif (previous_rsi <= self.config.RSI_OVERSOLD and 
                  current_rsi > self.config.RSI_OVERSOLD):
                signal_type = "oversold_exit"
                
            # Пересечение уровня перекупленности (70) снизу вверх (вход в зону)
            elif (previous_rsi < self.config.RSI_OVERBOUGHT and 
                  current_rsi >= self.config.RSI_OVERBOUGHT):
                signal_type = "overbought_enter"
                
            # Пересечение уровня перекупленности (70) сверху вниз (выход из зоны)
            elif (previous_rsi >= self.config.RSI_OVERBOUGHT and 
                  current_rsi < self.config.RSI_OVERBOUGHT):
                signal_type = "overbought_exit"
            
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
            

    def _is_duplicate_signal(self, signal: Dict) -> bool:
        """Проверка на дублирование сигнала"""
        try:
            symbol = signal['symbol']
            timeframe = signal['timeframe'] 
            signal_type = signal['signal_type']
            current_time = signal['timestamp']
            
            # Проверяем последние сигналы за 3 минуты
            recent_signals = self.database.get_recent_signals(symbol, timeframe, hours_back=0.05)  # 3 минуты
            
            for recent_signal in recent_signals:
                if recent_signal.get('signal_type') == signal_type:
                    # Проверяем временную близость
                    signal_time = recent_signal.get('timestamp', '')
                    if isinstance(signal_time, str):
                        signal_time = pd.to_datetime(signal_time)
                    current_time_pd = pd.to_datetime(current_time)
                    
                    # Если разница менее 2 минут - считаем дублем
                    if abs((signal_time - current_time_pd).total_seconds()) < 120:
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
            # Определяем стрелку в зависимости от зоны RSI
            arrow_map = {
                'oversold_enter': '↓',    # Вход в зону перепроданности
                'oversold_exit': '↓',     # Выход из зоны перепроданности (все о перепроданности = ↓)
                'overbought_enter': '↑',  # Вход в зону перекупленности  
                'overbought_exit': '↑'    # Выход из зоны перекупленности (все о перекупленности = ↑)
            }
            
            signal_type = signal['signal_type']
            arrow = arrow_map.get(signal_type, '')
            
            if not arrow:
                return ""
            
            # Простой формат: название монеты + стрелка
            symbol_clean = signal['symbol'].replace('USDT', '')
            
            return f"{symbol_clean} {arrow}"
            
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
                
            # Уведомляем о всех пересечениях границ RSI
            notify_signals = ['oversold_enter', 'oversold_exit', 'overbought_enter', 'overbought_exit']
            
            is_notify = signal['signal_type'] in notify_signals
            
            if is_notify:
                logger.info(f"Отправляем уведомление для сигнала: {signal['symbol']} {signal['signal_type']}")
            
            return is_notify
            
        except Exception as e:
            logger.error(f"Ошибка при проверке необходимости уведомления: {str(e)}")
            return False 