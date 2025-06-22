import asyncio
import logging
from datetime import datetime
from typing import List, Dict
from aiogram import Bot
from connectors.hybrid_connector import HybridConnector
from database import RSIDatabase
from rsi_analyzer import RSIAnalyzer
from web_interface import WebInterface
import config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RSIBot:
    def __init__(self):
        """Инициализация RSI бота"""
        self.config = config
        self.is_running = False
        
        # Проверяем переменные окружения
        config.validate_config()
        
        # Инициализация компонентов
        self.database = RSIDatabase(config.DATABASE_URL)
        self.hybrid_connector = HybridConnector(config)
        self.rsi_analyzer = RSIAnalyzer(config, self.database)
        self.telegram_bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        
        # Веб-интерфейс
        self.web_interface = WebInterface(config, self.database, self)
        
        # Настройки из базы данных
        self.current_symbols = config.DEFAULT_SYMBOLS
        self.current_timeframe = config.DEFAULT_TIMEFRAME
        self.current_oversold = config.RSI_OVERSOLD
        self.current_overbought = config.RSI_OVERBOUGHT
        
        logger.info("RSI бот инициализирован")
        

            
    async def update_settings(self):
        """Обновление настроек из базы данных"""
        try:
            user_settings = self.database.get_user_settings()
            if user_settings:
                self.current_symbols = user_settings['symbols']
                self.current_timeframe = user_settings['timeframe']
                self.current_oversold = user_settings['rsi_oversold']
                self.current_overbought = user_settings['rsi_overbought']
                
                # Обновляем настройки в анализаторе
                self.rsi_analyzer.config.RSI_OVERSOLD = self.current_oversold
                self.rsi_analyzer.config.RSI_OVERBOUGHT = self.current_overbought
                
                logger.info(f"Настройки обновлены: {len(self.current_symbols)} символов, "
                           f"таймфрейм {self.current_timeframe}")
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении настроек: {str(e)}")
            
    async def send_telegram_notification(self, signal: Dict):
        """Отправка уведомления в Telegram всем одобренным пользователям"""
        try:
            # Формируем сообщение
            message = self.rsi_analyzer.get_signal_description(signal)
            
            # Добавляем ссылку на TradingView
            tv_url = self.rsi_analyzer.get_tradingview_url(
                signal['symbol'], 
                signal['timeframe']
            )
            message += f"\n\n📊 [Открыть на TradingView]({tv_url})"
            
            # Получаем всех одобренных пользователей
            approved_users = self.database.get_approved_telegram_users()
            
            # Добавляем администратора, если его нет в списке
            admin_id = int(self.config.TELEGRAM_CHAT_ID)
            admin_in_list = any(user['user_id'] == admin_id for user in approved_users)
            
            if not admin_in_list:
                approved_users.append({
                    'user_id': admin_id,
                    'username': 'admin',
                    'first_name': 'Администратор',
                    'last_name': ''
                })
            
            # Отправляем сообщение всем одобренным пользователям
            sent_count = 0
            for user in approved_users:
                try:
                    # Для приватных чатов user_id = chat_id
                    await self.telegram_bot.send_message(
                        chat_id=user['user_id'],
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю {user['user_id']}: {str(e)}")
                    
            logger.info(f"Уведомление отправлено {sent_count}/{len(approved_users)} пользователям: {signal['symbol']} {signal['signal_type']}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {str(e)}")
            
    async def analyze_symbol(self, symbol: str):
        """Анализ одного символа"""
        try:
            # Получаем исторические данные
            df = await self.hybrid_connector.get_historical_data(
                symbol=symbol,
                timeframe=self.current_timeframe,
                limit=50
            )
            
            if df is None or len(df) < 2:
                logger.warning(f"Недостаточно данных для {symbol}")
                return
                
            # Анализируем RSI сигналы
            signals = self.rsi_analyzer.analyze_rsi_signals(
                symbol=symbol,
                timeframe=self.current_timeframe,
                df=df
            )
            
            # Отправляем уведомления для найденных сигналов
            for signal in signals:
                if self.rsi_analyzer.should_notify(signal):
                    await self.send_telegram_notification(signal)
                    
        except Exception as e:
            logger.error(f"Ошибка при анализе {symbol}: {str(e)}")
            

            
    async def run_analysis_cycle(self):
        """Один цикл анализа всех символов"""
        try:
            logger.info(f"Начинаем анализ {len(self.current_symbols)} символов")
            
            # Анализируем каждый символ
            for symbol in self.current_symbols:
                await self.analyze_symbol(symbol)
                await asyncio.sleep(1.5)  # Пауза для rate limiting
                
            logger.info("Цикл анализа завершен")
            
        except Exception as e:
            logger.error(f"Ошибка в цикле анализа: {str(e)}")
            
    async def start(self):
        """Запуск бота"""
        try:
            self.is_running = True
            logger.info("🚀 RSI бот запущен")
            
            # Обновляем настройки из базы данных
            await self.update_settings()
            
            # Запускаем веб-сервер в фоновом режиме
            self.web_server_task = asyncio.create_task(self.web_interface.start_server())
            logger.info(f"Веб-сервер запущен на http://{self.config.WEB_HOST}:{self.config.WEB_PORT}")
            
            # Основной цикл работы
            while self.is_running:
                try:
                    await self.run_analysis_cycle()
                    await asyncio.sleep(self.config.CHECK_INTERVAL)
                    
                except Exception as e:
                    logger.error(f"Ошибка в основном цикле: {str(e)}")
                    await asyncio.sleep(60)  # Пауза при ошибке
                    
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        except Exception as e:
            logger.error(f"Критическая ошибка: {str(e)}")
        finally:
            await self.stop()
            
    async def stop(self):
        """Остановка бота"""
        try:
            self.is_running = False
            logger.info("🛑 Остановка RSI бота")
            
            # Останавливаем веб-сервер
            if hasattr(self, 'web_server_task') and self.web_server_task:
                self.web_server_task.cancel()
                try:
                    await self.web_server_task
                except asyncio.CancelledError:
                    pass
            
            # Закрываем соединения
            if hasattr(self.telegram_bot, 'session') and self.telegram_bot.session:
                await self.telegram_bot.session.close()
                
            if self.hybrid_connector:
                self.hybrid_connector.close()
                
            logger.info("✅ RSI бот остановлен")
            
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {str(e)}")

async def main():
    """Основная функция"""
    try:
        logger.info("🔄 Запуск RSI бота...")
        
        # Создаем и запускаем бота
        bot = RSIBot()
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка в main: {str(e)}")
    finally:
        logger.info("Программа завершена")

if __name__ == "__main__":
    asyncio.run(main()) 