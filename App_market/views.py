from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .services import (
    get_exchange,
    get_ticker, 
    get_all_tickers, 
    get_order_book, 
    get_klines,
    get_exchange_info,
    get_historical_prices
)
import json
import logging
import time

logger = logging.getLogger(__name__)


_live_price_cache = {}  
LIVE_PRICE_TTL = 2 

@never_cache
def live_price_view(request):
    """
    Получить текущую цену пары с кешем 2 сек (для live-обновлений графика)
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    if '/' not in symbol:
        return JsonResponse({'error': 'Неверный формат'}, status=400)

    now = time.time()
    cached = _live_price_cache.get(symbol)
    if cached and (now - cached[0]) < LIVE_PRICE_TTL:
        return JsonResponse({'success': True, 'data': cached[1]})

    ticker = get_ticker(symbol)
    if ticker:
        data = {
            'symbol': ticker.get('symbol', symbol),
            'price': str(ticker.get('price', 0)),
            'high': str(ticker.get('high', 0)),
            'low': str(ticker.get('low', 0)),
            'volume': str(ticker.get('volume', 0)),
            'change': str(ticker.get('change', 0)),
        }
        _live_price_cache[symbol] = (now, data)
        return JsonResponse({'success': True, 'data': data})

    if cached:
        return JsonResponse({'success': True, 'data': cached[1]})

    return JsonResponse({'success': False, 'error': f'Не удалось получить цену для {symbol}'}, status=500)


@cache_page(30)
def price_view(request):
    """
    Получить цену одной пары
    GET /api/price/?symbol=BTC/USDT
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    
   
    if '/' not in symbol:
        return JsonResponse({'error': 'Неверный формат. Используйте BTC/USDT'}, status=400)
    
    ticker = get_ticker(symbol)
    if ticker:
        return JsonResponse({
            'success': True,
            'data': ticker
        })
    return JsonResponse({
        'success': False,
        'error': f'Не удалось получить цену для {symbol}'
    }, status=500)


@cache_page(30)
def prices_view(request):
    """
    Получить цены всех популярных пар
    GET /api/prices/
    """
    tickers = get_all_tickers()
    return JsonResponse({
        'success': True,
        'count': len(tickers),
        'data': tickers
    })


@cache_page(10)
def order_book_view(request):
    """
    Получить стакан заказов
    GET /api/orderbook/?symbol=BTC/USDT&limit=10
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    limit = int(request.GET.get('limit', 10))
    
    if '/' not in symbol:
        return JsonResponse({'error': 'Неверный формат. Используйте BTC/USDT'}, status=400)
    
    order_book = get_order_book(symbol, limit)
    if order_book:
        return JsonResponse({
            'success': True,
            'symbol': symbol,
            'bids': order_book['bids'],
            'asks': order_book['asks']
        })
    return JsonResponse({
        'success': False,
        'error': f'Не удалось получить стакан для {symbol}'
    }, status=500)


@cache_page(60)
def klines_view(request):
    """
    Получить исторические свечи
    GET /api/klines/?symbol=BTC/USDT&timeframe=1h&limit=100
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    timeframe = request.GET.get('timeframe', '1h')
    limit = int(request.GET.get('limit', 100))
    
    if '/' not in symbol:
        return JsonResponse({'error': 'Неверный формат. Используйте BTC/USDT'}, status=400)
    
    
    if limit > 1000:
        limit = 1000
    
    klines = get_klines(symbol, timeframe, limit)
    if klines:
        return JsonResponse({
            'success': True,
            'symbol': symbol,
            'timeframe': timeframe,
            'count': len(klines),
            'data': klines
        })
    return JsonResponse({
        'success': False,
        'error': f'Не удалось получить свечи для {symbol}'
    }, status=500)


def exchange_info_view(request):
    """
    Получить информацию о бирже (все пары, лимиты)
    GET /api/exchange-info/
    """
    info = get_exchange_info()
    if info:
        return JsonResponse({
            'success': True,
            'data': info
        })
    return JsonResponse({
        'success': False,
        'error': 'Не удалось получить информацию о бирже'
    }, status=500)


def search_symbols_view(request):
    """
    Поиск торговых пар
    GET /api/search/?q=BTC
    """
    query = request.GET.get('q', '').upper()
    if not query:
        return JsonResponse({'error': 'Укажите поисковый запрос'}, status=400)
    
    exchange = get_exchange()
    if not exchange:
        return JsonResponse({'error': 'Ошибка подключения к бирже'}, status=500)
    
    try:
        markets = exchange.load_markets()
        symbols = [s for s in markets.keys() if query in s and '/USDT' in s]
        symbols = sorted(symbols)[:20] 
        
        return JsonResponse({
            'success': True,
            'query': query,
            'count': len(symbols),
            'data': symbols
        })
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return JsonResponse({'error': str(e)}, status=500)