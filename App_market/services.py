import ccxt
import logging
import time
import requests
from decimal import Decimal
from decouple import config

logger = logging.getLogger(__name__)

_exchange_instance = None
_exchange_created_at = 0
_time_offset = 0


def _sync_time():
    """
    Синхронизирует локальное время с серверным временем Binance.
    Вычисляет разницу (offset) и применяет её ко всем запросам.
    """
    global _time_offset
    try:
        before = time.time()
        resp = requests.get('https://api.binance.com/api/v3/time', timeout=5)
        after = time.time()
        if resp.status_code == 200:
            server_time = resp.json()['serverTime'] / 1000.0
            local_time = (before + after) / 2.0
            _time_offset = server_time - local_time
            logger.info(f"Время синхронизировано. Offset: {_time_offset:.3f} сек")
        else:
            logger.warning(f"Не удалось синхронизировать время: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"Ошибка синхронизации времени: {e}")
        _time_offset = 0


def get_exchange():
    """
    Возвращает синглтон подключения к Binance.
    Создаётся один раз и живёт на протяжении всего времени работы сервера.
    """
    global _exchange_instance, _exchange_created_at
    if _exchange_instance is not None and (time.time() - _exchange_created_at) < 21600:
        return _exchange_instance

    _sync_time()

    try:
        _exchange_instance = ccxt.binance({
            'apiKey': config('BINANCE_API_KEY', default=''),
            'secret': config('BINANCE_SECRET_KEY', default=''),
            'enableRateLimit': True,
            'recvWindow': 60000,
            'options': {
                'defaultType': 'spot',
            }
        })

        if _time_offset:
            _exchange_instance.options['timestampOffset'] = int(_time_offset * 1000)

        _exchange_created_at = time.time()
        logger.info("Exchange singleton создан/обновлён")
        return _exchange_instance
    except Exception as e:
        logger.error(f"Ошибка подключения к Binance: {e}")
        _exchange_instance = None
        return None


_tickers_cache = {}
_tickers_cache_time = 0
TICKERS_CACHE_TTL = 5


def get_ticker(symbol='BTC/USDT'):
    """
    Получает текущую цену пары.
    Использует batch-кеш чтобы не спамить Binance.
    """
    global _tickers_cache, _tickers_cache_time
    now = time.time()

    if _tickers_cache and (now - _tickers_cache_time) < TICKERS_CACHE_TTL:
        cached = _tickers_cache.get(symbol)
        if cached:
            return cached

    try:
        exchange = get_exchange()
        if not exchange:
            return _tickers_cache.get(symbol)

        ticker = exchange.fetch_ticker(symbol)

        result = {
            'symbol': ticker.get('symbol', symbol),
            'price': Decimal(str(ticker.get('last', 0) or 0)),
            'high': Decimal(str(ticker.get('high', 0) or 0)),
            'low': Decimal(str(ticker.get('low', 0) or 0)),
            'volume': Decimal(str(ticker.get('quoteVolume', ticker.get('volume', 0)) or 0)),
            'change': Decimal(str(ticker.get('percentage', 0) or 0)),
        }
        _tickers_cache[symbol] = result
        _tickers_cache_time = now
        return result
    except Exception as e:
        logger.error(f"Ошибка получения цены {symbol}: {e}")
        global _exchange_instance, _exchange_created_at
        _exchange_instance = None
        _exchange_created_at = 0
        return _tickers_cache.get(symbol)


def get_all_tickers():
    """
    Получает цены всех популярных пар (одним запросом)
    """
    symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']
    try:
        exchange = get_exchange()
        if not exchange:
            return []

        tickers = exchange.fetch_tickers(symbols)
        result = []
        for symbol in symbols:
            t = tickers.get(symbol)
            if t:
                result.append({
                    'symbol': t.get('symbol', symbol),
                    'price': Decimal(str(t.get('last', 0) or 0)),
                    'high': Decimal(str(t.get('high', 0) or 0)),
                    'low': Decimal(str(t.get('low', 0) or 0)),
                    'volume': Decimal(str(t.get('quoteVolume', t.get('volume', 0)) or 0)),
                    'change': Decimal(str(t.get('percentage', 0) or 0)),
                })
        return result
    except Exception as e:
        logger.error(f"Ошибка получения тикеров: {e}")
        return []


def get_order_book(symbol='BTC/USDT', limit=10):
    """
    Получает стакан заказов
    """
    try:
        exchange = get_exchange()
        if not exchange:
            return None

        order_book = exchange.fetch_order_book(symbol, limit)

        return {
            'bids': order_book.get('bids', []),
            'asks': order_book.get('asks', []),
        }
    except Exception as e:
        logger.error(f"Ошибка получения стакана {symbol}: {e}")
        return None


_klines_cache = {}
KLINES_CACHE_TTL = 30


def get_klines(symbol='BTC/USDT', timeframe='1h', limit=100):
    """
    Получает исторические свечи с кешем
    """
    now = time.time()
    cache_key = (symbol, timeframe, limit)
    cached = _klines_cache.get(cache_key)
    if cached and (now - cached[0]) < KLINES_CACHE_TTL:
        return cached[1]

    try:
        exchange = get_exchange()
        if not exchange:
            if cached:
                return cached[1]
            return None

        klines = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        result = []
        for k in klines:
            result.append({
                'timestamp': k[0],
                'open': Decimal(str(k[1])),
                'high': Decimal(str(k[2])),
                'low': Decimal(str(k[3])),
                'close': Decimal(str(k[4])),
                'volume': Decimal(str(k[5])),
            })

        _klines_cache[cache_key] = (now, result)
        return result
    except Exception as e:
        logger.error(f"Ошибка получения свечей {symbol}: {e}")
        if cached:
            return cached[1]
        return None


def get_exchange_info():
    try:
        exchange = get_exchange()
        if not exchange:
            return None

        markets = exchange.load_markets()

        symbols = []
        for symbol, data in markets.items():
            if '/USDT' in symbol:
                symbols.append({
                    'symbol': symbol,
                    'base': data.get('base', ''),
                    'quote': data.get('quote', ''),
                    'active': data.get('active', True),
                })

        return {
            'total_symbols': len(symbols),
            'symbols': sorted(symbols, key=lambda x: x['symbol'])[:100],
        }
    except Exception as e:
        logger.error(f"Ошибка получения информации о бирже: {e}")
        return None


def get_all_tickers_for_balance(account):
    assets = [asset for asset in account.balance.keys() if asset != 'USDT']
    result = {}

    for asset in assets:
        ticker = get_ticker(f"{asset}/USDT")
        if ticker:
            result[asset] = ticker['price']

    return result

def get_historical_prices(symbol='BTC/USDT', limit=100):
    return get_klines(symbol, '1h', limit)
