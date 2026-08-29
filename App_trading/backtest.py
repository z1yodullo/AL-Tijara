from decimal import Decimal
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


def run_backtest(user, strategy_type, symbol, timeframe, period_days, params=None):
    """
    Запускает бэктестинг стратегии на исторических данных.
    Принимает тип стратегии, символ, таймфрейм и период.
    Возвращает результаты бэктестинга: сделки, доходность, просадку.
    """
    from App_market.services import get_klines
    from App_trading.indicators import (
        calculate_rsi, calculate_macd, calculate_bollinger_bands,
        get_composite_signal
    )
    from App_analytics.models import BacktestStrategy, BacktestResult

    if params is None:
        params = {}

    limit_map = {'1h': 24 * period_days, '4h': 6 * period_days, '1d': period_days}
    limit = limit_map.get(timeframe, 24 * period_days)

    klines = get_klines(symbol, timeframe, min(limit, 1000))
    if not klines or len(klines) < 50:
        return None

    closes = [float(k['close']) for k in klines]
    timestamps = [k['timestamp'] for k in klines]

    initial_capital = 10000.0
    capital = initial_capital
    position = 0.0
    entry_price = 0.0

    trades = []
    equity_curve = [{'timestamp': timestamps[0], 'value': initial_capital}]
    max_equity = initial_capital
    max_drawdown = 0.0

    rsi_period = params.get('rsi_period', 14)
    rsi_overbought = params.get('rsi_overbought', 70)
    rsi_oversold = params.get('rsi_oversold', 30)

    rsi_values = calculate_rsi(closes, rsi_period)
    macd_data = calculate_macd(closes)
    bollinger = calculate_bollinger_bands(closes)

    for i in range(max(rsi_period, 26) + 1, len(closes)):
        current_price = closes[i]

        indicators = {
            'rsi': rsi_values[:i+1],
            'macd': {
                'macd': macd_data['macd'][:i+1],
                'signal': macd_data['signal'][:i+1],
                'histogram': macd_data['histogram'][:i+1],
            },
            'bollinger': {
                'upper': bollinger['upper'][:i+1],
                'middle': bollinger['middle'][:i+1],
                'lower': bollinger['lower'][:i+1],
            },
        }

        signal = get_composite_signal(indicators, current_price)

        if signal['direction'] == 'buy' and position == 0.0:
            quantity = capital / current_price
            position = quantity
            entry_price = current_price
            capital = 0.0
            trades.append({
                'timestamp': timestamps[i],
                'action': 'BUY',
                'price': current_price,
                'quantity': round(quantity, 8),
                'value': round(capital + position * current_price, 2),
            })

        elif signal['direction'] == 'sell' and position > 0.0:
            sell_value = position * current_price
            capital = sell_value
            profit_pct = ((current_price - entry_price) / entry_price) * 100
            trades.append({
                'timestamp': timestamps[i],
                'action': 'SELL',
                'price': current_price,
                'quantity': round(position, 8),
                'profit_pct': round(profit_pct, 4),
                'value': round(capital, 2),
            })
            position = 0.0
            entry_price = 0.0

        equity = capital + position * current_price
        equity_curve.append({'timestamp': timestamps[i], 'value': round(equity, 2)})

        if equity > max_equity:
            max_equity = equity
        drawdown = ((max_equity - equity) / max_equity) * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    final_value = capital + position * closes[-1]
    total_return = ((final_value - initial_capital) / initial_capital) * 100

    winning_trades = len([t for t in trades if t.get('profit_pct', 0) > 0])
    losing_trades = len([t for t in trades if t.get('profit_pct', 0) < 0])
    total_trades_count = winning_trades + losing_trades
    win_rate = (winning_trades / total_trades_count * 100) if total_trades_count > 0 else 0

    strategy = BacktestStrategy.objects.create(
        user=user,
        name=f"{strategy_type} {symbol} {timeframe}",
        symbol=symbol,
        strategy_type=strategy_type,
        params=params,
        timeframe=timeframe,
        period_days=period_days,
    )

    result = BacktestResult.objects.create(
        strategy=strategy,
        total_trades=total_trades_count,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        total_return=round(total_return, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=0.0,
        win_rate=round(win_rate, 2),
        equity_curve=equity_curve,
        trades_log=trades,
    )

    logger.info(
        f"Backtest complete: {user.username} | {strategy_type} {symbol} | "
        f"Return: {total_return}% | Trades: {total_trades_count}"
    )
    return result
