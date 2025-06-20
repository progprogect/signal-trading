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
        """Анализ RSI сигналов для символа"""
        try:
            if df is None or len(df) < 2:
                return []
                
            signals = []
            
            # Получаем последние два значения RSI для определения пересечения
            current_rsi = df['rsi'].iloc[-1]
            previous_rsi = df['rsi'].iloc[-2]
            current_price = df['close'].iloc[-1]
            current_time = df.index[-1]
            
            # Создаем ключ для отслеживания состояния
            state_key = f"{symbol}_{timeframe}"
            
            # Проверяем на пересечение границ RSI
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
                    'previous_rsi': previous_rsi
                }
                
                signals.append(signal)
                
                # Сохраняем сигнал в базу данных
                self.database.add_signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    rsi_value=current_rsi,
                    price=current_price,
                    timestamp=current_time
                )
                
                logger.info(f"RSI сигнал: {symbol} {timeframe} {signal_type} "
                           f"RSI: {previous_rsi:.2f} -> {current_rsi:.2f}")
            
            # Обновляем состояние
            self.previous_rsi_states[state_key] = {
                'rsi': current_rsi,
                'timestamp': current_time
            }
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка при анализе RSI для {symbol}: {str(e)}")
            return []
            
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
            signal_descriptions = {
                'oversold_enter': '🔴 *ПЕРЕПРОДАН!* RSI ушел ниже 30',
                'overbought_enter': '🟡 *ПЕРЕКУПЛЕН!* RSI поднялся выше 70'
            }
            
            signal_type = signal['signal_type']
            description = signal_descriptions.get(signal_type, 'Неизвестный сигнал')
            
            # Только для входов в зоны - выходы не показываем
            if signal_type not in ['oversold_enter', 'overbought_enter']:
                return ""
            
            historical_mark = " (исторический)" if signal.get('historical', False) else ""
            
            # Добавляем эмодзи в зависимости от символа
            symbol_emoji = {
                'BTCUSDT': '₿', 'ETHUSDT': 'Ξ', 'DOGEUSDT': '🐕',
                'ADAUSDT': '🌟', 'SOLUSDT': '☀️', 'XRPUSDT': '💧',
                'DOTUSDT': '🔴', 'AVAXUSDT': '🏔️', 'MATICUSDT': '🔷'
            }.get(signal['symbol'], '💰')
            
            # Форматируем время
            try:
                if hasattr(signal['timestamp'], 'strftime'):
                    time_str = signal['timestamp'].strftime('%H:%M:%S')
                else:
                    time_str = str(signal['timestamp'])[:19]
            except:
                time_str = str(signal['timestamp'])
            
            return (f"{description}{historical_mark}\n\n"
                   f"{symbol_emoji} *{signal['symbol'].replace('USDT', '')}*\n"
                   f"📈 RSI: *{signal['rsi_value']:.2f}*\n"
                   f"💰 Цена: *${signal['price']:.4f}*\n"
                   f"⏰ {time_str} | {signal['timeframe']}")
            
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