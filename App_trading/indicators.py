import pandas as pd
import numpy as np
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def calculate_sma(closes, period=20):
    """
    Рассчитывает Simple Moving Average (простую скользящую среднюю).
    Принимает список цен закрытия и период.
    Возвращает список значений SMA (первые period-1 значений = NaN).
    """
    series = pd.Series([float(c) for c in closes])
    return series.rolling(window=period).mean().tolist()


def calculate_ema(closes, period=20):
    """
    Рассчитывает Exponential Moving Average (экспоненциальную скользящую среднюю).
    Более чувствительна к последним ценам, чем SMA.
    """
    series = pd.Series([float(c) for c in closes])
    return series.ewm(span=period, adjust=False).mean().tolist()


def calculate_rsi(closes, period=14):
    """
    Рассчитывает Relative Strength Index (индекс относительной силы).
    Определяет перекупленность (>70) и перепроданность (<30).
    Возвращает список значений от 0 до 100.
    """
    series = pd.Series([float(c) for c in closes])
    delta = series.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.tolist()


def calculate_macd(closes, fast=12, slow=26, signal=9):
    """
    Рассчитывает MACD (Moving Average Convergence Divergence).
    Возвращает словарь с тремя списками:
      - macd: линия MACD (разница быстрой и медленной EMA)
      - signal: сигнальная линия (EMA от MACD)
      - histogram: гистограмма (разница MACD и signal)
    """
    series = pd.Series([float(c) for c in closes])

    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        'macd': macd_line.tolist(),
        'signal': signal_line.tolist(),
        'histogram': histogram.tolist(),
    }


def calculate_bollinger_bands(closes, period=20, std_dev=2):
    """
    Рассчитывает Bollinger Bands (полосы Боллинджера).
    Состоят из трёх линий:
      - upper: верхняя полоса (SMA + N стандартных отклонений)
      - middle: средняя линия (SMA)
      - lower: нижняя полоса (SMA - N стандартных отклонений)
    """
    series = pd.Series([float(c) for c in closes])

    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return {
        'upper': upper.tolist(),
        'middle': middle.tolist(),
        'lower': lower.tolist(),
    }


def calculate_atr(highs, lows, closes, period=14):
    """
    Рассчитывает Average True Range (средний истинный диапазон).
    Используется для определения волатильности рынка.
    """
    high_series = pd.Series([float(h) for h in highs])
    low_series = pd.Series([float(l) for l in lows])
    close_series = pd.Series([float(c) for c in closes])

    prev_close = close_series.shift(1)

    tr1 = high_series - low_series
    tr2 = (high_series - prev_close).abs()
    tr3 = (low_series - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr.tolist()


def calculate_stochastic(highs, lows, closes, k_period=14, d_period=3):
    """
    Рассчитывает Stochastic Oscillator (осциллятор Стохастика).
    Возвращает словарь:
      - k: линия %K (быстрая)
      - d: линия %D (медленная, SMA от %K)
    Значения от 0 до 100. Перекупленность >80, перепроданность <20.
    """
    high_series = pd.Series([float(h) for h in highs])
    low_series = pd.Series([float(l) for l in lows])
    close_series = pd.Series([float(c) for c in closes])

    lowest_low = low_series.rolling(window=k_period).min()
    highest_high = high_series.rolling(window=k_period).max()

    k_line = ((close_series - lowest_low) / (highest_high - lowest_low)) * 100
    d_line = k_line.rolling(window=d_period).mean()

    return {
        'k': k_line.tolist(),
        'd': d_line.tolist(),
    }


def calculate_all_indicators(klines):
    """
    Рассчитывает все индикаторы одновременно на основе исторических свечей.
    Принимает список словарей с ключами open, high, low, close.
    Возвращает словарь со всеми рассчитанными индикаторами.
    """
    closes = [float(k['close']) for k in klines]
    highs = [float(k['high']) for k in klines]
    lows = [float(k['low']) for k in klines]

    return {
        'sma_20': calculate_sma(closes, 20),
        'sma_50': calculate_sma(closes, 50),
        'ema_12': calculate_ema(closes, 12),
        'ema_26': calculate_ema(closes, 26),
        'rsi': calculate_rsi(closes),
        'macd': calculate_macd(closes),
        'bollinger': calculate_bollinger_bands(closes),
        'atr': calculate_atr(highs, lows, closes),
        'stochastic': calculate_stochastic(highs, lows, closes),
    }


def get_rsi_signal(rsi_value):
    """
    Генерирует торговый сигнал на основе RSI.
    RSI > 70 = перекупленность (продажа).
    RSI < 30 = перепроданность (покупка).
    Иначе = нейтральная зона.
    """
    if rsi_value is None or np.isnan(rsi_value):
        return 'neutral'
    if rsi_value > 70:
        return 'sell'
    elif rsi_value < 30:
        return 'buy'
    return 'neutral'


def get_macd_signal(macd_data):
    """
    Генерирует торговый сигнал на основе MACD.
    Если гистограмма > 0 и растёт = покупка.
    Если гистограмма < 0 и падает = продажа.
    """
    histogram = macd_data.get('histogram', [])
    if len(histogram) < 2:
        return 'neutral'

    current = histogram[-1]
    previous = histogram[-2]

    if current is None or previous is None:
        return 'neutral'
    if np.isnan(current) or np.isnan(previous):
        return 'neutral'

    if current > 0 and current > previous:
        return 'buy'
    elif current < 0 and current < previous:
        return 'sell'
    return 'neutral'


def get_bollinger_signal(price, bollinger_data):
    """
    Генерирует торговый сигнал на основе Bollinger Bands.
    Если цена ниже нижней полосы = покупка (перепроданность).
    Если цена выше верхней полосы = продажа (перекупленность).
    """
    upper = bollinger_data.get('upper', [])
    lower = bollinger_data.get('lower', [])

    if not upper or not lower:
        return 'neutral'

    current_upper = upper[-1]
    current_lower = lower[-1]

    if current_upper is None or current_lower is None:
        return 'neutral'
    if np.isnan(current_upper) or np.isnan(current_lower):
        return 'neutral'

    price_float = float(price)

    if price_float < current_lower:
        return 'buy'
    elif price_float > current_upper:
        return 'sell'
    return 'neutral'


def get_composite_signal(indicators, current_price):
    """
    Рассчитывает общий торговый сигнал на основе всех индикаторов.
    Суммирует голоса buy/sell от каждого индикатора.
    Возвращает словарь с направлением и силой сигнала.
    """
    signals = []

    rsi_vals = indicators.get('rsi', [])
    if rsi_vals:
        signals.append(get_rsi_signal(rsi_vals[-1]))

    macd_data = indicators.get('macd', {})
    if macd_data:
        signals.append(get_macd_signal(macd_data))

    bollinger_data = indicators.get('bollinger', {})
    if bollinger_data:
        signals.append(get_bollinger_signal(current_price, bollinger_data))

    buy_count = signals.count('buy')
    sell_count = signals.count('sell')
    total = len(signals) if signals else 1

    if buy_count > sell_count:
        direction = 'buy'
        strength = buy_count / total
    elif sell_count > buy_count:
        direction = 'sell'
        strength = sell_count / total
    else:
        direction = 'neutral'
        strength = 0

    return {
        'direction': direction,
        'strength': round(strength, 2),
        'signals': signals,
        'buy_votes': buy_count,
        'sell_votes': sell_count,
        'neutral_votes': signals.count('neutral'),
    }
