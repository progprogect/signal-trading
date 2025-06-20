# Настройки Binance API
BINANCE_API_KEY = "Wz1vXKRIJ463tMV2o8Qf5zuWLB5J0MuipMBWC4zlICOc4wk6gPhCniihNmy7iya6"
BINANCE_API_SECRET = "9lEl9x3ayEHJ5RwRzCMG3Td3BG8ggsnt50S67emGKnMctihEKZORGWM51aCpmEd1"

# Настройки TradingView
TRADINGVIEW_USERNAME = ""
TRADINGVIEW_PASSWORD = ""

# Настройки Telegram
TELEGRAM_BOT_TOKEN = "7818586285:AAHGM-RP1-fn2fPhlJM6w1OPU8PJa8HbUMI"
TELEGRAM_CHAT_ID = "319719503"

# Символы для анализа (только поддерживаемые Kraken)
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "DOGEUSDT", "ADAUSDT", "SOLUSDT", 
    "XRPUSDT", "DOTUSDT", "AVAXUSDT", "MATICUSDT"
]

# Настройки RSI
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Таймфреймы для анализа
AVAILABLE_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
DEFAULT_TIMEFRAME = "5m"

# Настройки веб-интерфейса
WEB_HOST = "127.0.0.1"
WEB_PORT = 8081

# Настройки базы данных
DATABASE_PATH = "rsi_signals.db"

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