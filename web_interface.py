import json
import logging
from datetime import datetime
from typing import List, Dict
from aiohttp import web, web_request
from aiohttp_jinja2 import template, setup as jinja2_setup
import jinja2
import aiohttp_cors
from database import RSIDatabase
import asyncio

logger = logging.getLogger(__name__)

class WebInterface:
    def __init__(self, config, database: RSIDatabase, rsi_bot=None):
        """Инициализация веб-интерфейса"""
        self.config = config
        self.database = database
        self.rsi_bot = rsi_bot
        self.app = web.Application()
        self.setup_jinja2()
        self.setup_cors()
        self.setup_routes()
        
    def setup_jinja2(self):
        """Настройка шаблонизатора Jinja2"""
        jinja2_setup(self.app, loader=jinja2.FileSystemLoader('templates'))
        
    def setup_cors(self):
        """Настройка CORS"""
        self.cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
            
    def setup_routes(self):
        """Настройка маршрутов"""
        # Health check для Railway
        self.cors.add(self.app.router.add_get('/health', self.health_check))
        
        # Добавляем маршруты
        self.cors.add(self.app.router.add_get('/', self.index))
        self.cors.add(self.app.router.add_get('/api/signals', self.get_signals_api))
        self.cors.add(self.app.router.add_get('/api/signals/{symbol}', self.get_signals_by_symbol_api))
        self.cors.add(self.app.router.add_get('/api/historical/{symbol}/{days}', self.get_historical_signals_api))
        self.cors.add(self.app.router.add_get('/api/settings', self.get_settings_api))
        self.cors.add(self.app.router.add_post('/api/settings', self.save_settings_api))
        self.cors.add(self.app.router.add_get('/api/status', self.get_status_api))
        
        # API для получения текущих RSI значений
        self.cors.add(self.app.router.add_get('/api/current_rsi', self.get_current_rsi_api))
        
        # API для управления пользователями Telegram
        self.cors.add(self.app.router.add_get('/api/telegram_users', self.get_telegram_users_api))
        self.cors.add(self.app.router.add_post('/api/telegram_users', self.add_telegram_user_api))
        self.cors.add(self.app.router.add_post('/api/telegram_users/{user_id}/approve', self.approve_telegram_user_api))
        self.cors.add(self.app.router.add_post('/api/telegram_users/{user_id}/block', self.block_telegram_user_api))
        self.cors.add(self.app.router.add_delete('/api/telegram_users/{user_id}', self.delete_telegram_user_api))
        
        self.app.router.add_static('/static', 'static')
        
    @template('index.html')
    async def index(self, request: web_request.Request):
        """Главная страница"""
        try:
            # Получаем последние сигналы
            recent_signals = self.database.get_recent_signals(50)
            
            # Получаем настройки пользователя
            user_settings = self.database.get_user_settings()
            if not user_settings:
                user_settings = {
                    'symbols': self.config.DEFAULT_SYMBOLS,
                    'timeframe': self.config.DEFAULT_TIMEFRAME,
                    'rsi_oversold': self.config.RSI_OVERSOLD,
                    'rsi_overbought': self.config.RSI_OVERBOUGHT,
                    'notifications_enabled': True
                }
            
            return {
                'signals': recent_signals,
                'settings': user_settings,
                'available_timeframes': self.config.AVAILABLE_TIMEFRAMES,
                'default_symbols': self.config.DEFAULT_SYMBOLS
            }
            
        except Exception as e:
            logger.error(f"Ошибка в главной странице: {str(e)}")
            return {'error': str(e)}
            
    async def get_signals_api(self, request: web_request.Request):
        """API для получения сигналов"""
        try:
            limit = int(request.query.get('limit', 100))
            signals = self.database.get_recent_signals(limit)
            
            # Конвертируем datetime в строку для JSON
            for signal in signals:
                if isinstance(signal['timestamp'], datetime):
                    signal['timestamp'] = signal['timestamp'].isoformat()
                    
            return web.json_response(signals)
            
        except Exception as e:
            logger.error(f"Ошибка в API сигналов: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def get_signals_by_symbol_api(self, request: web_request.Request):
        """API для получения сигналов по символу"""
        try:
            symbol = request.match_info['symbol']
            limit = int(request.query.get('limit', 50))
            
            signals = self.database.get_signals_by_symbol(symbol, limit)
            
            # Конвертируем datetime в строку для JSON
            for signal in signals:
                if isinstance(signal['timestamp'], datetime):
                    signal['timestamp'] = signal['timestamp'].isoformat()
                    
            return web.json_response(signals)
            
        except Exception as e:
            logger.error(f"Ошибка в API сигналов по символу: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def get_historical_signals_api(self, request: web_request.Request):
        """API для получения исторических RSI сигналов"""
        try:
            symbol = request.match_info['symbol']
            days = int(request.match_info['days'])
            
            # Ограничиваем максимальный период
            if days > 30:
                days = 30
                
            if not self.rsi_bot or not hasattr(self.rsi_bot, 'kraken_connector'):
                return web.json_response({'error': 'RSI бот не инициализирован'}, status=500)
                
            # Получаем настройки пользователя для таймфрейма
            user_settings = self.database.get_user_settings()
            timeframe = user_settings['timeframe'] if user_settings else self.config.DEFAULT_TIMEFRAME
            
            # Получаем исторические данные с большим лимитом для анализа
            limit = max(500, days * 24 * (60 // int(timeframe.replace('m', '').replace('h', '*60').replace('d', '*1440'))))
            
            df = await self.rsi_bot.kraken_connector.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            if df is None:
                return web.json_response({'error': f'Нет данных для {symbol}'}, status=404)
                
            # Анализируем исторические сигналы
            historical_signals = self.rsi_bot.rsi_analyzer.analyze_historical_rsi_signals(
                symbol=symbol,
                timeframe=timeframe,
                df=df,
                days_back=days
            )
            
            # Конвертируем datetime в строку для JSON
            for signal in historical_signals:
                if isinstance(signal['timestamp'], datetime):
                    signal['timestamp'] = signal['timestamp'].isoformat()
                    
            logger.info(f"Найдено {len(historical_signals)} исторических сигналов для {symbol} за {days} дней")
            
            return web.json_response({
                'symbol': symbol,
                'days': days,
                'timeframe': timeframe,
                'signals': historical_signals,
                'total_signals': len(historical_signals)
            })
            
        except Exception as e:
            logger.error(f"Ошибка в API исторических сигналов: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def get_settings_api(self, request: web_request.Request):
        """API для получения настроек"""
        try:
            settings = self.database.get_user_settings()
            if not settings:
                settings = {
                    'symbols': self.config.DEFAULT_SYMBOLS,
                    'timeframe': self.config.DEFAULT_TIMEFRAME,
                    'rsi_oversold': self.config.RSI_OVERSOLD,
                    'rsi_overbought': self.config.RSI_OVERBOUGHT,
                    'notifications_enabled': True
                }
                
            return web.json_response(settings)
            
        except Exception as e:
            logger.error(f"Ошибка в API настроек: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def save_settings_api(self, request: web_request.Request):
        """API для сохранения настроек"""
        try:
            data = await request.json()
            
            symbols = data.get('symbols', self.config.DEFAULT_SYMBOLS)
            timeframe = data.get('timeframe', self.config.DEFAULT_TIMEFRAME)
            
            # Валидация символов
            if not isinstance(symbols, list) or len(symbols) == 0:
                return web.json_response({'error': 'Необходимо указать хотя бы одну монету для анализа'}, status=400)
            
            # Проверяем корректность символов
            valid_symbols = []
            for symbol in symbols:
                symbol = symbol.strip().upper()
                if not symbol:
                    continue
                if not symbol.endswith('USDT'):
                    symbol += 'USDT'
                if len(symbol) >= 5 and symbol.endswith('USDT'):
                    valid_symbols.append(symbol)
                else:
                    return web.json_response({'error': f'Неверный формат символа: {symbol}. Используйте формат BTCUSDT'}, status=400)
            
            if len(valid_symbols) == 0:
                return web.json_response({'error': 'Не найдено ни одного корректного символа'}, status=400)
                
            if timeframe not in self.config.AVAILABLE_TIMEFRAMES:
                return web.json_response({'error': 'Неверный таймфрейм'}, status=400)
            
            # RSI уровни берем из конфигурации (не изменяются пользователем)
            rsi_oversold = self.config.RSI_OVERSOLD
            rsi_overbought = self.config.RSI_OVERBOUGHT
            
            # Сохраняем настройки
            success = self.database.save_user_settings(
                symbols=valid_symbols,
                timeframe=timeframe,
                rsi_oversold=rsi_oversold,
                rsi_overbought=rsi_overbought
            )
            
            if success:
                # Обновляем настройки в боте, если он запущен
                if self.rsi_bot:
                    await self.rsi_bot.update_settings()
                    
                return web.json_response({'success': True})
            else:
                return web.json_response({'error': 'Ошибка сохранения настроек'}, status=500)
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении настроек: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def get_status_api(self, request: web_request.Request):
        """API для получения статуса бота"""
        try:
            status = {
                'running': self.rsi_bot is not None and self.rsi_bot.is_running if hasattr(self.rsi_bot, 'is_running') else False,
                'last_check': datetime.now().isoformat(),
                'total_signals': len(self.database.get_recent_signals(1000)),
                'database_connected': True
            }
            
            return web.json_response(status)
            
        except Exception as e:
            logger.error(f"Ошибка в API статуса: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_current_rsi_api(self, request: web_request.Request):
        """API для получения текущих значений RSI"""
        try:
            if not self.rsi_bot or not hasattr(self.rsi_bot, 'rsi_analyzer'):
                return web.json_response({'error': 'RSI бот не инициализирован'}, status=500)
            
            # Получаем настройки пользователя
            user_settings = self.database.get_user_settings()
            if not user_settings:
                return web.json_response({'error': 'Настройки не найдены'}, status=404)
            
            symbols = user_settings.get('symbols', [])
            if not symbols:
                return web.json_response({'error': 'Символы для анализа не настроены'}, status=404)
            
            current_rsi_data = []
            
            # Получаем текущие RSI значения через rsi_analyzer
            for symbol in symbols:
                try:
                    # Получаем данные через гибридный коннектор
                    user_settings = self.database.get_user_settings()
                    timeframe = user_settings.get('timeframe', self.config.DEFAULT_TIMEFRAME) if user_settings else self.config.DEFAULT_TIMEFRAME
                    df = await self.rsi_bot.hybrid_connector.get_historical_data(symbol, timeframe, 50)
                    
                    if df is not None and not df.empty and 'rsi' in df.columns:
                        # RSI уже вычислен в DataFrame
                        if len(df) > 0 and not df['rsi'].empty:
                            current_rsi = float(df['rsi'].iloc[-1])
                            current_price = float(df['close'].iloc[-1])
                            
                            # Определяем статус RSI
                            if current_rsi <= self.config.RSI_OVERSOLD:
                                status = 'oversold'
                                status_text = 'Перепродано'
                                status_color = 'success'
                            elif current_rsi >= self.config.RSI_OVERBOUGHT:
                                status = 'overbought'
                                status_text = 'Перекуплено'
                                status_color = 'danger'
                            else:
                                status = 'neutral'
                                status_text = 'Нейтрально'
                                status_color = 'secondary'
                            
                            current_rsi_data.append({
                                'symbol': symbol,
                                'rsi': round(current_rsi, 2),
                                'price': round(current_price, 8),
                                'status': status,
                                'status_text': status_text,
                                'status_color': status_color,
                                'timestamp': datetime.now().isoformat()
                            })
                        else:
                            logger.warning(f"Не удалось получить RSI для {symbol} - пустые данные")
                            # Добавляем символ как недоступный
                            current_rsi_data.append({
                                'symbol': symbol,
                                'rsi': None,
                                'price': None,
                                'status': 'unavailable',
                                'status_text': 'N/A',
                                'status_color': 'secondary',
                                'timestamp': datetime.now().isoformat()
                            })
                    else:
                        logger.warning(f"Нет данных для {symbol} или отсутствует колонка RSI")
                        # Добавляем символ как недоступный
                        current_rsi_data.append({
                            'symbol': symbol,
                            'rsi': None,
                            'price': None,
                            'status': 'unavailable',
                            'status_text': 'N/A',
                            'status_color': 'secondary',
                            'timestamp': datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    logger.warning(f"Данные для {symbol} временно недоступны: {str(e)}")
                    # Добавляем символ как недоступный
                    current_rsi_data.append({
                        'symbol': symbol,
                        'rsi': None,
                        'price': None,
                        'status': 'unavailable',
                        'status_text': 'N/A',
                        'status_color': 'secondary',
                        'timestamp': datetime.now().isoformat()
                    })
            
            return web.json_response({
                'symbols': current_rsi_data,
                'total_symbols': len(symbols),
                'successful': len([s for s in current_rsi_data if s['status'] not in ['unavailable', 'error']]),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Ошибка в API текущих RSI: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def get_telegram_users_api(self, request: web_request.Request):
        """API для получения пользователей Telegram"""
        try:
            users = self.database.get_telegram_users()
            return web.json_response(users)
            
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей Telegram: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def add_telegram_user_api(self, request: web_request.Request):
        """API для добавления пользователя Telegram вручную"""
        try:
            data = await request.json()
            
            user_id = data.get('user_id')
            username = data.get('username', '')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            
            # Валидация user_id
            if not user_id:
                return web.json_response({'error': 'User ID обязателен'}, status=400)
                
            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({'error': 'User ID должен быть числом'}, status=400)
                
            # Проверяем, нет ли уже такого пользователя
            existing_status = self.database.get_telegram_user_status(user_id)
            if existing_status:
                return web.json_response({'error': f'Пользователь с ID {user_id} уже существует (статус: {existing_status})'}, status=409)
            
            # Добавляем пользователя
            success = self.database.add_telegram_user(
                user_id=user_id,
                username=username.strip() if username else None,
                first_name=first_name.strip() if first_name else None,
                last_name=last_name.strip() if last_name else None
            )
            
            if success:
                logger.info(f"Пользователь {user_id} добавлен администратором")
                return web.json_response({'success': True, 'message': f'Пользователь {user_id} добавлен на модерацию'})
            else:
                return web.json_response({'error': 'Ошибка при добавлении пользователя'}, status=500)
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя Telegram: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def approve_telegram_user_api(self, request: web_request.Request):
        """API для одобрения пользователя Telegram"""
        try:
            user_id = int(request.match_info['user_id'])
            
            success = self.database.update_telegram_user_status(user_id, 'approved')
            
            if success:
                # Уведомляем пользователя об одобрении (для приватных чатов user_id = chat_id)
                try:
                    if self.rsi_bot and self.rsi_bot.telegram_bot:
                        await self.rsi_bot.telegram_bot.send_message(
                            chat_id=user_id,
                            text="✅ Ваша заявка одобрена!\n\n"
                                 "Теперь вы будете получать RSI сигналы о важных движениях на рынке.\n"
                                 "Добро пожаловать в систему торговых сигналов!"
                        )
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении пользователя об одобрении: {str(e)}")
                
                return web.json_response({'success': True})
            else:
                return web.json_response({'error': 'Пользователь не найден'}, status=404)
                
        except Exception as e:
            logger.error(f"Ошибка при одобрении пользователя: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def block_telegram_user_api(self, request: web_request.Request):
        """API для блокировки пользователя Telegram"""
        try:
            user_id = int(request.match_info['user_id'])
            
            success = self.database.update_telegram_user_status(user_id, 'blocked')
            
            if success:
                # Уведомляем пользователя о блокировке (для приватных чатов user_id = chat_id)
                try:
                    if self.rsi_bot and self.rsi_bot.telegram_bot:
                        await self.rsi_bot.telegram_bot.send_message(
                            chat_id=user_id,
                            text="🚫 Доступ к боту ограничен\n\n"
                                 "Ваша заявка была отклонена администратором.\n"
                                 "Если у вас есть вопросы, обратитесь к администратору."
                        )
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении пользователя о блокировке: {str(e)}")
                
                return web.json_response({'success': True})
            else:
                return web.json_response({'error': 'Пользователь не найден'}, status=404)
                
        except Exception as e:
            logger.error(f"Ошибка при блокировке пользователя: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def delete_telegram_user_api(self, request: web_request.Request):
        """API для удаления пользователя Telegram"""
        try:
            user_id = int(request.match_info['user_id'])
            
            success = self.database.delete_telegram_user(user_id)
            
            if success:
                return web.json_response({'success': True})
            else:
                return web.json_response({'error': 'Пользователь не найден'}, status=404)
                
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def health_check(self, request: web_request.Request):
        """Простой health check для Railway"""
        return web.json_response({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'service': 'RSI Trading Bot'
        })
            
    async def start_server(self):
        """Запуск веб-сервера"""
        try:
            runner = web.AppRunner(self.app)
            await runner.setup()
            
            site = web.TCPSite(runner, self.config.WEB_HOST, self.config.WEB_PORT)
            await site.start()
            
            logger.info(f"Веб-сервер запущен на http://{self.config.WEB_HOST}:{self.config.WEB_PORT}")
            
            # Возвращаем управление, но сохраняем ссылки для корректного завершения
            self.runner = runner
            self.site = site
            
            # Ждем бесконечно (пока не будет остановлен)
            try:
                while True:
                    await asyncio.sleep(3600)  # Проверяем каждый час
            except asyncio.CancelledError:
                logger.info("Веб-сервер получил сигнал остановки")
                await runner.cleanup()
            
        except Exception as e:
            logger.error(f"Ошибка при запуске веб-сервера: {str(e)}")
            raise 