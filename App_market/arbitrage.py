from decimal import Decimal
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def find_arbitrage_opportunities():
    """
    Ищет арбитражные возможности между торговыми парами.
    Сравнивает цены BTC/USDT с价格 ETH/BTC * ETH/USDT
    и аналогичные комбинации для выявления расхождений.
    Возвращает список найденных возможностей.
    """
    from App_market.services import get_ticker

    pairs = [
        ('BTC/USDT', 'ETH/USDT', 'ETH/BTC'),
        ('BTC/USDT', 'BNB/USDT', 'BNB/BTC'),
        ('ETH/USDT', 'BNB/USDT', 'BNB/ETH'),
    ]

    opportunities = []

    for pair_a, pair_b, pair_cross in pairs:
        ticker_a = get_ticker(pair_a)
        ticker_b = get_ticker(pair_b)
        ticker_cross = get_ticker(pair_cross)

        if not all([ticker_a, ticker_b, ticker_cross]):
            continue

        price_a = float(ticker_a['price'])
        price_b = float(ticker_b['price'])
        price_cross = float(ticker_cross['price'])

        implied_price = price_b / price_cross
        spread_pct = ((implied_price - price_a) / price_a) * 100

        if abs(spread_pct) > 0.1:
            direction = 'buy_a_sell_b' if spread_pct > 0 else 'buy_b_sell_a'
            opportunities.append({
                'pair_a': pair_a,
                'pair_b': pair_b,
                'pair_cross': pair_cross,
                'price_a': price_a,
                'price_b': price_b,
                'price_cross': price_cross,
                'implied_price': round(implied_price, 8),
                'spread_pct': round(spread_pct, 4),
                'direction': direction,
            })

    return sorted(opportunities, key=lambda x: abs(x['spread_pct']), reverse=True)


def find_triangular_arbitrage():
    """
    Ищет треугольный арбитраж: USDT → BTC → ETH → USDT.
    Если начальная и конечная суммы отличаются больше чем на 0.1%, есть возможность.
    """
    from App_market.services import get_ticker

    btc_usdt = get_ticker('BTC/USDT')
    eth_btc = get_ticker('ETH/BTC')
    eth_usdt = get_ticker('ETH/USDT')

    if not all([btc_usdt, eth_btc, eth_usdt]):
        return None

    start_amount = 10000.0
    btc_amount = start_amount / float(btc_usdt['price'])
    eth_amount = btc_amount * float(eth_btc['price'])
    final_amount = eth_amount * float(eth_usdt['price'])

    profit_pct = ((final_amount - start_amount) / start_amount) * 100

    return {
        'start_amount': start_amount,
        'final_amount': round(final_amount, 2),
        'profit_pct': round(profit_pct, 4),
        'route': 'USDT → BTC → ETH → USDT',
        'path': [
            {'pair': 'BTC/USDT', 'action': 'BUY', 'amount': btc_amount},
            {'pair': 'ETH/BTC', 'action': 'BUY', 'amount': eth_amount},
            {'pair': 'ETH/USDT', 'action': 'SELL', 'amount': final_amount},
        ],
    }


def calculate_spread(symbol_a, symbol_b):
    """
    Рассчитывает спред между двумя торговыми парами.
    Возвращает разницу цен в процентах.
    """
    from App_market.services import get_ticker

    ticker_a = get_ticker(symbol_a)
    ticker_b = get_ticker(symbol_b)

    if not ticker_a or not ticker_b:
        return None

    price_a = float(ticker_a['price'])
    price_b = float(ticker_b['price'])

    spread = price_a - price_b
    spread_pct = (spread / price_a) * 100

    return {
        'symbol_a': symbol_a,
        'symbol_b': symbol_b,
        'price_a': price_a,
        'price_b': price_b,
        'spread': round(spread, 8),
        'spread_pct': round(spread_pct, 4),
    }
