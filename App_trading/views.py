from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from decimal import Decimal
import json
import logging
import time

from App_users.models import DemoAccount, DemoOrder, RealAccount
from App_market.services import get_ticker, get_order_book, get_all_tickers, get_klines
from .services import execute_market_order, execute_limit_order, cancel_order
from App_trading.stop_loss import set_stop_loss_take_profit

logger = logging.getLogger(__name__)


@login_required
def dashboard_view(request):
    """
    Главный дашборд с балансом и ценами
    """
    account = request.user.demo_account
    real_account = request.user.real_account
    tickers = get_all_tickers()
    prices = {t['symbol'].split('/')[0]: t['price'] for t in tickers}
    account.calculate_total_value(prices)
    real_account.calculate_total_value(prices)
    open_orders = DemoOrder.objects.filter(
        account=account, 
        status='OPEN'
    ).order_by('-created_at')[:10]
    recent_trades = DemoOrder.objects.filter(
        account=account, 
        status='FILLED'
    ).order_by('-created_at')[:10]
    btc_price = next((t['price'] for t in tickers if t['symbol'] == 'BTC/USDT'), 0)
    
    context = {
        'balance': account.balance,
        'total_value': account.total_value_usdt,
        'real_balance': real_account.balance,
        'real_total_value': real_account.total_value_usdt,
        'tickers': tickers,
        'open_orders': open_orders,
        'recent_trades': recent_trades,
        'btc_price': btc_price,
    }
    
    return render(request, 'market/dashboard.html', context)


@login_required
def trading_view(request):
    """
    Торговая страница с созданием ордеров
    """
    account = request.user.demo_account
    real_account = request.user.real_account
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    ticker = get_ticker(symbol)
    
    if ticker:
        current_price = ticker['price']
        change_24h = ticker['change']
    else:
        current_price = 0
        change_24h = 0

    order_book = get_order_book(symbol) if ticker else {'bids': [], 'asks': []}
    open_orders = DemoOrder.objects.filter(
        account=account,
        symbol=symbol,
        status='OPEN'
    ).order_by('-created_at')
    

    history = DemoOrder.objects.filter(
        account=account,
        symbol=symbol,
        status='FILLED'
    ).order_by('-created_at')[:50]
    
    context = {
        'symbol': symbol,
        'current_price': current_price,
        'change_24h': change_24h,
        'order_book': order_book,
        'balance': account.balance,
        'real_balance': real_account.balance,
        'open_orders': open_orders,
        'history': history,
    }
    
    return render(request, 'trading/spot.html', context)


@login_required
@csrf_exempt
def create_order_view(request):
    """
    Создание ордера (API и POST)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)
    
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    except:
        data = request.POST
    
    symbol = data.get('symbol', 'BTC/USDT').upper()
    side = data.get('side', 'BUY').upper()
    order_type = data.get('order_type', 'MARKET').upper()
    quantity = Decimal(str(data.get('quantity', 0)))
    price = data.get('price')
    stop_loss = data.get('stop_loss')
    take_profit = data.get('take_profit')
    
    if quantity <= 0:
        messages.error(request, 'Количество должно быть больше 0')
        return redirect('trading:trading')
    
    if order_type == 'LIMIT':
        if not price:
            messages.error(request, 'Для лимитного ордера укажите цену')
            return redirect('trading:trading')
        price = Decimal(str(price))
        if price <= 0:
            messages.error(request, 'Цена должна быть больше 0')
            return redirect('trading:trading')
    
    account = request.user.demo_account
    
    try:
        with transaction.atomic():
            if order_type == 'MARKET':
                order = execute_market_order(account, symbol, side, quantity)
                messages.success(
                    request, 
                    f'✅ {side} {quantity} {symbol} по рыночной цене. ID: {order.id}'
                )
            else: 
                order = execute_limit_order(account, symbol, side, quantity, price)
                if stop_loss or take_profit:
                    set_stop_loss_take_profit(
                        order.id, request.user,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                messages.success(
                    request, 
                    f'✅ Лимитный ордер {side} {quantity} {symbol} по ${price:.2f} создан. ID: {order.id}'
                )
        
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Ошибка создания ордера: {e}")
        messages.error(request, f'Ошибка: {str(e)}')
    
    return redirect('trading:trading')


@login_required
@csrf_exempt
def cancel_order_view(request, order_id):
    """
    Отмена ордера
    """
    order = get_object_or_404(DemoOrder, id=order_id)
    
    if order.account.user != request.user:
        messages.error(request, 'У вас нет прав на отмену этого ордера')
        return redirect('trading:trading')
    
    if order.status != 'OPEN':
        messages.warning(request, f'Ордер уже {order.status}')
        return redirect('trading:trading')
    
    try:
        cancel_order(order.id)
        messages.success(request, f'✅ Ордер {order_id} отменен')
    except Exception as e:
        logger.error(f"Ошибка отмены ордера: {e}")
        messages.error(request, f'Ошибка: {str(e)}')
    
    return redirect('trading:trading')


@login_required
def history_view(request):
    """
    Полная история сделок с фильтрацией
    """
    account = request.user.demo_account
    real_account = request.user.real_account
    
    symbol = request.GET.get('symbol', '')
    side = request.GET.get('side', '')
    status = request.GET.get('status', '')
    
    orders = DemoOrder.objects.filter(account=account)
    
    if symbol:
        orders = orders.filter(symbol=symbol.upper())
    if side:
        orders = orders.filter(side=side.upper())
    if status:
        orders = orders.filter(status=status.upper())
    
    total_trades = orders.filter(status='FILLED').count()
    total_volume = sum(o.price * o.quantity for o in orders.filter(status='FILLED'))
    buy_count = orders.filter(side='BUY', status='FILLED').count()
    sell_count = orders.filter(side='SELL', status='FILLED').count()
    
    context = {
        'orders': orders.order_by('-created_at'),
        'total_trades': total_trades,
        'total_volume': total_volume,
        'buy_count': buy_count,
        'sell_count': sell_count,
        'symbol_filter': symbol,
        'side_filter': side,
        'status_filter': status,
        'balance': account.balance,
        'real_balance': real_account.balance,
    }
    
    return render(request, 'trading/history.html', context)


@login_required
def reset_demo_account_view(request):
    """
    Сброс демо-счета (удалить все ордера и сбросить баланс)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)
    
    account = request.user.demo_account
    
    with transaction.atomic():
        DemoOrder.objects.filter(account=account).delete()
        
        from django.conf import settings
        account.balance = settings.DEMO_STARTING_BALANCE
        account.total_value_usdt = 0
        account.save()
    
    messages.success(request, '🔄 Демо-счет сброшен! Баланс восстановлен.')
    return redirect('trading:dashboard')


@login_required
def set_demo_balance_api(request):
    """
    API для установки баланса демо-счета.
    POST /api/demo/set-balance/ {"balance": 10000}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)

    try:
        data = json.loads(request.body)
        new_balance = float(data.get('balance', 0))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверные данные'}, status=400)

    if new_balance < 0:
        return JsonResponse({'error': 'Баланс не может быть отрицательным'}, status=400)

    account = request.user.demo_account
    account.balance = {'USDT': new_balance}
    account.total_value_usdt = new_balance
    account.save()

    return JsonResponse({'success': True, 'balance': new_balance})


@login_required
def trade_view(request):
    """
    Страница торговли в стиле Quotex.
    Полноэкранный график со свечами, индикаторами и панелью сделок.
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    account = request.user.demo_account
    real_account = request.user.real_account

    ticker = get_ticker(symbol)

    if ticker:
        current_price = str(ticker['price'])
        change_24h = str(ticker['change'])
    else:
        current_price = '0'
        change_24h = '0'

    available_pairs = [
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT',
        'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'DOT/USDT',
        'AVAX/USDT', 'LINK/USDT', 'MATIC/USDT', 'UNI/USDT',
    ]

    context = {
        'symbol': symbol,
        'current_price': current_price,
        'change_24h': change_24h,
        'balance': str(account.get_balance('USDT')),
        'real_balance': str(real_account.get_balance('USDT')),
        'available_pairs': available_pairs,
    }

    return render(request, 'trading/trade.html', context)


_klines_cache = {}  
KLINES_CACHE_TTL = 10 


@login_required
def trade_klines_api(request):
    """
    API для получения свечей для графика.
    GET /api/trade/klines/?symbol=BTC/USDT&timeframe=1m&limit=200
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    timeframe = request.GET.get('timeframe', '1m')
    limit = int(request.GET.get('limit', 200))

    tf_map = {
        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
        '1h': '1h', '4h': '4h', '1d': '1d',
    }
    timeframe = tf_map.get(timeframe, '1m')

    cache_key = (symbol, timeframe)
    now = time.time()
    cached = _klines_cache.get(cache_key)
    if cached and (now - cached[0]) < KLINES_CACHE_TTL:
        return JsonResponse({
            'candles': cached[1],
            'volumes': cached[2],
            'symbol': symbol,
            'timeframe': timeframe,
        })

    klines = get_klines(symbol, timeframe, min(limit, 500))
    if not klines:
        if cached:
            return JsonResponse({
                'candles': cached[1],
                'volumes': cached[2],
                'symbol': symbol,
                'timeframe': timeframe,
            })
        return JsonResponse({'error': 'Не удалось получить данные'}, status=500)

    candles = []
    volumes = []
    for k in klines:
        t = int(k['timestamp'] / 1000)
        candles.append({
            'time': t,
            'open': float(k['open']),
            'high': float(k['high']),
            'low': float(k['low']),
            'close': float(k['close']),
        })
        volumes.append({
            'time': t,
            'value': float(k['volume']),
            'color': 'rgba(14,203,129,0.3)' if float(k['close']) >= float(k['open']) else 'rgba(246,70,93,0.3)',
        })

    _klines_cache[cache_key] = (now, candles, volumes)

    return JsonResponse({
        'candles': candles,
        'volumes': volumes,
        'symbol': symbol,
        'timeframe': timeframe,
    })


@login_required
@csrf_exempt
def place_binary_trade(request):
    """
    Размещение сделки (.Call/Put) как в Quotex.
    POST /api/trade/place/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Неверный JSON'}, status=400)

    symbol = data.get('symbol', 'BTC/USDT').upper()
    direction = data.get('direction', '').upper()
    amount = Decimal(str(data.get('amount', 0)))
    duration = int(data.get('duration', 60))
    mode = data.get('mode', 'demo').lower()

    if direction not in ('CALL', 'PUT'):
        return JsonResponse({'error': 'Направление должно быть CALL или PUT'}, status=400)

    if amount <= 0:
        return JsonResponse({'error': 'Сумма ставки должна быть больше 0'}, status=400)

    account = request.user.demo_account if mode == 'demo' else request.user.real_account
    if account.get_balance('USDT') < amount:
        return JsonResponse({'error': 'Недостаточно средств'}, status=400)

    ticker = get_ticker(symbol)
    if not ticker:
        return JsonResponse({'error': f'Пара {symbol} не найдена'}, status=400)

    entry_price = float(ticker['price'])

    account.update_balance('USDT', -amount)

    order = DemoOrder.objects.create(
        account=account,
        symbol=symbol,
        side='BUY' if direction == 'CALL' else 'SELL',
        order_type='MARKET',
        price=Decimal(str(entry_price)),
        quantity=amount,
        filled_quantity=amount,
        status='OPEN',
    )

    from django.utils.timezone import now, timedelta
    import threading

    def resolve_trade():
        import time
        time.sleep(duration)
        try:
            current_ticker = get_ticker(symbol)
            if not current_ticker:
                return

            exit_price = float(current_ticker['price'])
            is_win = False

            if direction == 'CALL' and exit_price > entry_price:
                is_win = True
            elif direction == 'PUT' and exit_price < entry_price:
                is_win = True

            profit_pct = 87
            if is_win:
                payout = float(amount) * (1 + profit_pct / 100)
                account.update_balance('USDT', Decimal(str(payout)))
                order.status = 'FILLED'
                order.error_message = f'WIN +${payout:.2f}'
            else:
                order.status = 'CANCELLED'
                order.error_message = f'LOST -${float(amount):.2f}'

            order.filled_at = now()
            order.save()

        except Exception as e:
            logger.error(f"Trade resolve error: {e}")

    thread = threading.Thread(target=resolve_trade, daemon=True)
    thread.start()

    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'symbol': symbol,
        'direction': direction,
        'amount': str(amount),
        'entry_price': entry_price,
        'duration': duration,
        'balance': str(account.get_balance('USDT')),
    })


@login_required
def account_balance_api(request):
    """
    API для получения баланса.demo или реального счета.
    GET /api/trade/balance/?mode=demo|real
    """
    mode = request.GET.get('mode', 'demo').lower()

    if mode == 'real':
        account = request.user.real_account
    else:
        account = request.user.demo_account

    balance = account.get_balance('USDT')
    total_value = str(account.total_value_usdt) if account.total_value_usdt else str(balance)

    return JsonResponse({
        'balance': str(balance),
        'total_value': total_value,
        'mode': mode,
    })


@login_required
def trade_result_api(request):
    """
    API для получения результата сделки.
    GET /api/trade/result/?id=<order_id>
    """
    order_id = request.GET.get('id')
    if not order_id:
        return JsonResponse({'error': 'id обязателен'}, status=400)

    try:
        order = DemoOrder.objects.get(id=order_id, account__user=request.user)
    except DemoOrder.DoesNotExist:
        return JsonResponse({'error': 'Ордер не найден'}, status=404)

    return JsonResponse({
        'id': order.id,
        'status': order.status,
        'symbol': order.symbol,
        'side': order.side,
        'price': str(order.price) if order.price else None,
        'quantity': str(order.quantity),
        'error_message': order.error_message,
    })


_ANALYZE_CACHE = {}
ANALYZE_CACHE_TTL = 60

SCAN_PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT',
    'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT',
    'LINK/USDT', 'TON/USDT',
]

SCAN_TIMEFRAMES = ['5m', '15m', '1h']


def _safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        import math
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


@login_required
def market_analyze_api(request):
    """
    AI-анализатор рынка.
    GET /api/trade/analyze/
    """
    now = time.time()
    cached = _ANALYZE_CACHE.get('result')
    if cached and (now - cached['timestamp']) < ANALYZE_CACHE_TTL:
        return JsonResponse(cached)

    from .indicators import (
        calculate_rsi, calculate_macd, calculate_bollinger_bands,
        calculate_stochastic, calculate_ema, calculate_sma,
    )

    best_signals = []

    for symbol in SCAN_PAIRS:
        for tf in SCAN_TIMEFRAMES:
            try:
                klines = get_klines(symbol, tf, 100)
                if not klines or len(klines) < 30:
                    continue

                closes = [float(k['close']) for k in klines]
                highs = [float(k['high']) for k in klines]
                lows = [float(k['low']) for k in klines]
                current_price = closes[-1]
                prev_price = closes[-2] if len(closes) > 1 else current_price
                price_change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price else 0

                rsi = calculate_rsi(closes)
                macd = calculate_macd(closes)
                bollinger = calculate_bollinger_bands(closes)
                stoch = calculate_stochastic(highs, lows, closes)
                ema12 = calculate_ema(closes, 12)
                ema26 = calculate_ema(closes, 26)
                sma20 = calculate_sma(closes, 20)
                sma50 = calculate_sma(closes, 50)

                buy_score = 0
                sell_score = 0
                reasons_buy = []
                reasons_sell = []

                rsi_val = _safe_float(rsi[-1], 50) if rsi else 50
                if rsi_val < 30:
                    buy_score += 2
                    reasons_buy.append(f'RSI перепродан ({rsi_val:.0f})')
                elif rsi_val < 40:
                    buy_score += 1
                    reasons_buy.append(f'RSI низкий ({rsi_val:.0f})')
                elif rsi_val > 70:
                    sell_score += 2
                    reasons_sell.append(f'RSI перекуплен ({rsi_val:.0f})')
                elif rsi_val > 60:
                    sell_score += 1
                    reasons_sell.append(f'RSI высокий ({rsi_val:.0f})')

                hist = macd.get('histogram', [])
                if len(hist) >= 2:
                    h_curr = _safe_float(hist[-1])
                    h_prev = _safe_float(hist[-2])
                    if h_curr > 0 and h_curr > h_prev:
                        buy_score += 2
                        reasons_buy.append('MACD бычий рост')
                    elif h_curr > 0:
                        buy_score += 1
                        reasons_buy.append('MACD положительный')
                    elif h_curr < 0 and h_curr < h_prev:
                        sell_score += 2
                        reasons_sell.append('MACD медвежий рост')
                    elif h_curr < 0:
                        sell_score += 1
                        reasons_sell.append('MACD отрицательный')

                bb_upper = bollinger.get('upper', [])
                bb_lower = bollinger.get('lower', [])
                if bb_upper and bb_lower:
                    bu = _safe_float(bb_upper[-1], current_price)
                    bl = _safe_float(bb_lower[-1], current_price)
                    spread = bu - bl if bu != bl else 1
                    if current_price < bl:
                        buy_score += 2
                        reasons_buy.append('Цена ниже Bollinger')
                    elif current_price <= bl + spread * 0.15:
                        buy_score += 1
                        reasons_buy.append('Цена у нижней Bollinger')
                    elif current_price > bu:
                        sell_score += 2
                        reasons_sell.append('Цена выше Bollinger')
                    elif current_price >= bu - spread * 0.15:
                        sell_score += 1
                        reasons_sell.append('Цена у верхней Bollinger')

                sk = stoch.get('k', [])
                sd = stoch.get('d', [])
                if sk and sd and len(sk) >= 2 and len(sd) >= 2:
                    k_val = _safe_float(sk[-1], 50)
                    d_val = _safe_float(sd[-1], 50)
                    k_prev = _safe_float(sk[-2], 50)
                    if k_val < 20 and d_val < 20 and k_val > k_prev:
                        buy_score += 2
                        reasons_buy.append(f'Stoch перепродан ({k_val:.0f})')
                    elif k_val < 30:
                        buy_score += 1
                        reasons_buy.append(f'Stoch низкий ({k_val:.0f})')
                    elif k_val > 80 and d_val > 80 and k_val < k_prev:
                        sell_score += 2
                        reasons_sell.append(f'Stoch перекуплен ({k_val:.0f})')
                    elif k_val > 70:
                        sell_score += 1
                        reasons_sell.append(f'Stoch высокий ({k_val:.0f})')

                if ema12 and ema26 and len(ema12) >= 2 and len(ema26) >= 2:
                    e12 = _safe_float(ema12[-1])
                    e26 = _safe_float(ema26[-1])
                    e12_p = _safe_float(ema12[-2])
                    e26_p = _safe_float(ema26[-2])
                    if e12 > e26 and e12_p <= e26_p:
                        buy_score += 3
                        reasons_buy.append('EMA пересечение бычье')
                    elif e12 > e26:
                        buy_score += 1
                    elif e12 < e26 and e12_p >= e26_p:
                        sell_score += 3
                        reasons_sell.append('EMA пересечение медвежье')
                    elif e12 < e26:
                        sell_score += 1

                if sma20 and sma50 and len(sma20) >= 2 and len(sma50) >= 2:
                    s20 = _safe_float(sma20[-1])
                    s50 = _safe_float(sma50[-1])
                    if s20 > s50 and current_price > s20:
                        buy_score += 1
                        reasons_buy.append('Тренд бычий (SMA)')
                    elif s20 < s50 and current_price < s20:
                        sell_score += 1
                        reasons_sell.append('Тренд медвежий (SMA)')

                total_score = buy_score + sell_score
                if total_score == 0:
                    continue

                if buy_score > sell_score:
                    direction = 'CALL'
                    confidence = min(95, 40 + (buy_score - sell_score) * 8 + total_score * 2)
                    reasons = reasons_buy
                elif sell_score > buy_score:
                    direction = 'PUT'
                    confidence = min(95, 40 + (sell_score - buy_score) * 8 + total_score * 2)
                    reasons = reasons_sell
                else:
                    continue

                tf_multiplier = {'5m': 1.0, '15m': 1.05, '1h': 1.1}
                confidence = min(95, confidence * tf_multiplier.get(tf, 1.0))

                best_signals.append({
                    'symbol': symbol.replace('/', ''),
                    'symbol_display': symbol,
                    'timeframe': tf,
                    'direction': direction,
                    'confidence': round(confidence),
                    'score': buy_score if direction == 'CALL' else sell_score,
                    'price': round(current_price, 8) if current_price < 1 else round(current_price, 2),
                    'price_change': round(price_change_pct, 2),
                    'reasons': reasons[:4],
                    'rsi': round(rsi_val, 1),
                })

            except Exception as e:
                logger.error(f"Ошибка анализа {symbol} {tf}: {e}")
                continue

    best_signals.sort(key=lambda x: x['confidence'], reverse=True)
    top = best_signals[:5]

    pair_scores = {}
    for s in best_signals:
        p = s['symbol']
        if p not in pair_scores or s['confidence'] > pair_scores[p]['confidence']:
            pair_scores[p] = s

    pair_ranking = sorted(pair_scores.values(), key=lambda x: x['confidence'], reverse=True)[:8]

    result_data = {
        'success': True,
        'best_signal': top[0] if top else None,
        'signals': top,
        'pair_ranking': pair_ranking,
        'scanned': len(best_signals),
        'scan_time': round(time.time() - now, 1),
        'timestamp': now,
    }

    _ANALYZE_CACHE['result'] = result_data

    return JsonResponse({
        'success': True,
        'best_signal': top[0] if top else None,
        'signals': top,
        'pair_ranking': pair_ranking,
        'scanned': len(best_signals),
        'scan_time': round(time.time() - now, 1),
    })