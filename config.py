import os
from typing import List

# Настройки из переменных окружения (для Railway)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Настройки TradingView
TRADINGVIEW_USERNAME = os.getenv("TRADINGVIEW_USERNAME", "")
TRADINGVIEW_PASSWORD = os.getenv("TRADINGVIEW_PASSWORD", "")

# Настройки Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Символы для анализа (согласно требованиям пользователя)
DEFAULT_SYMBOLS = [
    'BTCUSDT', 'DOGEUSDT', 'PEPEUSDT', 'SUIUSDT', 
    'BIGTIMEUSDT', 'ALTUSDT', 'WLDUSDT'
]

# Настройки RSI
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Таймфреймы для анализа
AVAILABLE_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
DEFAULT_TIMEFRAME = "5m"

# Настройки веб-интерфейса (Railway автоматически назначает порт)
WEB_HOST = os.getenv("HOST", "0.0.0.0")  # 0.0.0.0 для Railway
WEB_PORT = int(os.getenv("PORT", "8081"))  # Railway устанавливает переменную PORT

# Настройки базы данных (PostgreSQL для Railway)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///rsi_signals.db")  # Fallback для локальной разработки

# Настройки уведомлений
CHECK_INTERVAL = 180  # секунд между проверками (3 минуты)

# Параметры канала
CHANNEL_TOUCHES_MIN = 4  # Минимальное количество касаний для построения канала
PRICE_PROXIMITY_THRESHOLD = 0.001  # 0.1% от границы канала

# Настройки уведомлений
NOTIFICATION_THRESHOLD = 0.02  # 2% изменение цены

# Параметры паттернов
PATTERN_CONFIRMATION_THRESHOLD = 0.005  # 0.5% для подтверждения паттерна

# Шаблон уведомления
NOTIFICATION_TEMPLATE = """🔔 *Сигнал для {symbol}*

💰 Текущая цена: {current_price:.2f}

{timeframes_analysis}

📊 *Общий анализ:*
{overall_analysis}

📈 [Открыть график]({chart_url})"""

PATTERNS = {
    "pin_bar": {
        "body_ratio": 0.3,  # Максимальное соотношение тела к теням
        "min_shadow_ratio": 2.0  # Минимальное соотношение теней к телу
    },
    "engulfing": {
        "min_body_ratio": 1.5  # Минимальное соотношение тел свечей
    },
    "double_top_bottom": {
        "price_tolerance": 0.002,  # 0.2% допустимое отклонение для двойных вершин/впадин
        "min_bars_between": 10  # Минимальное количество свечей между вершинами/впадинами
    },
    "morning_evening_star": {
        "gap_tolerance": 0.001  # 0.1% допустимый разрыв между свечами
    }
}

# Проверка обязательных переменных окружения
def validate_config():
    """Проверка наличия обязательных переменных окружения"""
    required_vars = {
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    
    return True 