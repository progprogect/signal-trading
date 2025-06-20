import requests
import pandas as pd
from datetime import datetime, timedelta
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from selenium.webdriver.common.keys import Keys
import webbrowser
import websocket
import json

logger = logging.getLogger(__name__)

class TradingViewConnector:
    def __init__(self):
        """Инициализация коннектора TradingView"""
        self.base_url = "https://www.tradingview.com/chart"
        self.username = None
        self.password = None
        self.driver = None
        
    def set_credentials(self, username, password):
        """Установка учетных данных"""
        self.username = username
        self.password = password
        
    def _login(self):
        """Вход в TradingView"""
        try:
            if not self.username or not self.password:
                logger.error("Учетные данные не установлены")
                return False
                
            # Инициализируем драйвер
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')  # Запуск в фоновом режиме
            self.driver = webdriver.Chrome(options=options)
            
            # Открываем страницу входа
            self.driver.get("https://www.tradingview.com/accounts/signin/")
            
            # Ждем загрузки формы входа
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_field = self.driver.find_element(By.NAME, "password")
            
            # Вводим учетные данные
            username_field.send_keys(self.username)
            password_field.send_keys(self.password)
            
            # Нажимаем кнопку входа
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Ждем успешного входа
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-header__user-menu-button"))
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при входе в TradingView: {str(e)}")
            return False
            
    def get_historical_data(self, symbol, timeframe):
        """Получение исторических данных"""
        try:
            # Преобразование таймфрейма в формат Binance
            interval = self._convert_timeframe(timeframe)
            
            # Получение данных
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
            
            params = {
                'symbol': symbol,
                'interval': interval,
                'startTime': start_time,
                'endTime': end_time,
                'limit': 500
            }
            
            response = requests.get(f"{self.base_url}/klines", params=params)
            if response.status_code != 200:
                print(f"Ошибка при получении данных: {response.text}")
                return None
                
            data = response.json()
            
            # Преобразование данных в DataFrame
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Преобразование типов данных
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            return df
            
        except Exception as e:
            print(f"Ошибка при получении данных: {e}")
            return None
            
    def get_current_price(self, symbol):
        """Получение текущей цены"""
        try:
            response = requests.get(f"{self.base_url}/ticker/price", params={'symbol': symbol})
            if response.status_code != 200:
                print(f"Ошибка при получении текущей цены: {response.text}")
                return None
                
            data = response.json()
            return float(data['price'])
            
        except Exception as e:
            print(f"Ошибка при получении текущей цены: {e}")
            return None
            
    def generate_tv_link(self, symbol, timeframe):
        """Генерация ссылки на график"""
        # Преобразуем таймфрейм в формат TradingView
        timeframe_map = {
            '15m': '15',
            '1h': '60',
            '4h': '240',
            '1d': 'D'
        }
        
        tv_timeframe = timeframe_map.get(timeframe, '60')
        return f"{self.base_url}/?symbol=BINANCE:{symbol}&interval={tv_timeframe}"
        
    def _convert_timeframe(self, timeframe):
        """Преобразование таймфрейма в формат Binance"""
        timeframe_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        return timeframe_map.get(timeframe, '1h')
        
    def _convert_timeframe_to_tv(self, timeframe):
        """Преобразование таймфрейма в формат TradingView"""
        timeframe_map = {
            '1m': '1',
            '5m': '5',
            '15m': '15',
            '30m': '30',
            '1h': '60',
            '4h': '240',
            '1d': 'D'
        }
        return timeframe_map.get(timeframe, '60')
        
    def draw_levels(self, symbol, timeframe, levels):
        """Рисование уровней на графике"""
        try:
            # Формируем URL для рисования уровней
            chart_url = self.generate_tv_link(symbol, timeframe)
            
            # Добавляем параметры для рисования уровней
            levels_param = ','.join([f"{level:.2f}" for level in levels])
            chart_url += f"&drawing_tool=horizontal_line&levels={levels_param}&color=#2196F3&linewidth=2&style=1"
            
            # Открываем график в браузере
            webbrowser.open(chart_url)
            
            logger.info(f"Открыт график с уровнями: {chart_url}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при рисовании уровней: {str(e)}")
            return False
            
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None 