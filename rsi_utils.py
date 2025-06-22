"""
Утилиты для расчета RSI без pandas-ta (запасной вариант)
"""
import pandas as pd
import numpy as np


def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """
    Расчет RSI (Relative Strength Index) с помощью pandas
    
    Args:
        data: Серия цен закрытия
        period: Период для расчета RSI (по умолчанию 14)
    
    Returns:
        Серия со значениями RSI
    """
    # Расчет изменений цены
    delta = data.diff()
    
    # Разделение на прибыли и убытки
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Расчет средних значений с помощью скользящего среднего
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    
    # Расчет RS (Relative Strength)
    rs = avg_gain / avg_loss
    
    # Расчет RSI
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_rsi_with_ema(data: pd.Series, period: int = 14) -> pd.Series:
    """
    Расчет RSI с экспоненциальным скользящим средним (более точный)
    
    Args:
        data: Серия цен закрытия
        period: Период для расчета RSI (по умолчанию 14)
    
    Returns:
        Серия со значениями RSI
    """
    # Расчет изменений цены
    delta = data.diff()
    
    # Разделение на прибыли и убытки
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Расчет экспоненциального скользящего среднего
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    
    # Расчет RS (Relative Strength)
    rs = avg_gain / avg_loss
    
    # Расчет RSI
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def add_rsi_to_dataframe(df: pd.DataFrame, close_column: str = 'close', period: int = 14) -> pd.DataFrame:
    """
    Добавление RSI к DataFrame
    
    Args:
        df: DataFrame с данными OHLCV
        close_column: Название колонки с ценами закрытия
        period: Период для расчета RSI
    
    Returns:
        DataFrame с добавленной колонкой RSI
    """
    df = df.copy()
    df['rsi'] = calculate_rsi_with_ema(df[close_column], period)
    return df 