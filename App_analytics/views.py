from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import json
import logging

from App_analytics.models import PriceAlert, BacktestStrategy, BacktestResult, TradeSnapshot, TradingStats
from App_analytics.services import create_alert, delete_alert, check_alerts
from App_users.models import DemoOrder, DemoAccount, Watchlist
from App_market.services import get_ticker, get_all_tickers, get_klines
from App_market.arbitrage import find_arbitrage_opportunities, find_triangular_arbitrage
from App_trading.indicators import calculate_all_indicators, get_composite_signal
from App_trading.backtest import run_backtest

logger = logging.getLogger(__name__)


@login_required
def alerts_view(request):
    """
    Страница управления ценовыми алертами.
    Показывает активные и сработавшие алерты пользователя.
    """
    user_alerts = PriceAlert.objects.filter(user=request.user).order_by('-created_at')
    active_alerts = user_alerts.filter(is_triggered=False)
    triggered_alerts = user_alerts.filter(is_triggered=True)[:20]

    return render(request, 'analytics/alerts.html', {
        'active_alerts': active_alerts,
        'triggered_alerts': triggered_alerts,
    })


@login_required
@csrf_exempt
def create_alert_view(request):
    """
    API для создания ценового алерта.
    Принимает POST с symbol, target_price, direction.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    except Exception:
        data = request.POST

    symbol = data.get('symbol', '').upper()
    target_price = data.get('target_price')
    direction = data.get('direction', 'ABOVE').upper()

    if not symbol or not target_price:
        messages.error(request, 'Укажите символ и целевую цену')
        return redirect('analytics:alerts')

    if direction not in ('ABOVE', 'BELOW'):
        messages.error(request, 'Направление должно быть ABOVE или BELOW')
        return redirect('analytics:alerts')

    try:
        create_alert(request.user, symbol, target_price, direction)
        messages.success(request, f'Алерт создан: {symbol} {direction} {target_price}')
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        messages.error(request, f'Ошибка: {str(e)}')

    return redirect('analytics:alerts')


@login_required
@csrf_exempt
def delete_alert_view(request, alert_id):
    """
    API для удаления ценового алерта.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)

    try:
        delete_alert(request.user, alert_id)
        messages.success(request, 'Алерт удален')
    except Exception as e:
        messages.error(request, f'Ошибка: {str(e)}')

    return redirect('analytics:alerts')


@login_required
def check_alerts_view(request):
    """
    API для ручной проверки алертов.
    Возвращает количество сработавших алертов.
    """
    triggered = check_alerts()
    return JsonResponse({'triggered': triggered})


@login_required
def watchlist_view(request):
    """
    Страница списка отслеживаемых торговых пар.
    """
    user_watchlist = Watchlist.objects.filter(user=request.user).order_by('-added_at')

    watchlist_with_prices = []
    for item in user_watchlist:
        ticker = get_ticker(item.symbol)
        watchlist_with_prices.append({
            'id': item.id,
            'symbol': item.symbol,
            'added_at': item.added_at,
            'price': ticker['price'] if ticker else None,
            'change': ticker['change'] if ticker else None,
        })

    return render(request, 'analytics/watchlist.html', {
        'watchlist': watchlist_with_prices,
    })


@login_required
@csrf_exempt
def add_to_watchlist_view(request):
    """
    API для добавления торговой пары в watchlist.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    except Exception:
        data = request.POST

    symbol = data.get('symbol', '').upper()
    if not symbol:
        messages.error(request, 'Укажите символ')
        return redirect('analytics:watchlist')

    ticker = get_ticker(symbol)
    if not ticker:
        messages.error(request, f'Торговая пара {symbol} не найдена')
        return redirect('analytics:watchlist')

    _, created = Watchlist.objects.get_or_create(user=request.user, symbol=symbol)
    if created:
        messages.success(request, f'{symbol} добавлен в watchlist')
    else:
        messages.info(request, f'{symbol} уже в watchlist')

    return redirect('analytics:watchlist')


@login_required
@csrf_exempt
def remove_from_watchlist_view(request, item_id):
    """
    API для удаления торговой пары из watchlist.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)

    try:
        item = Watchlist.objects.get(id=item_id, user=request.user)
        item.delete()
        messages.success(request, 'Удалено из watchlist')
    except Watchlist.DoesNotExist:
        messages.error(request, 'Элемент не найден')

    return redirect('analytics:watchlist')


@login_required
def arbitrage_view(request):
    """
    Страница мониторинга арбитражных возможностей.
    """
    opportunities = find_arbitrage_opportunities()
    triangular = find_triangular_arbitrage()

    return render(request, 'analytics/arbitrage.html', {
        'opportunities': opportunities,
        'triangular': triangular,
    })


@login_required
def backtest_view(request):
    """
    Страница бэктестинга стратегий.
    Показывает форму запуска и результаты предыдущих тестов.
    """
    user_strategies = BacktestStrategy.objects.filter(user=request.user).order_by('-created_at')[:10]
    recent_results = BacktestResult.objects.filter(
        strategy__user=request.user
    ).order_by('-created_at')[:5]

    return render(request, 'analytics/backtest.html', {
        'strategies': user_strategies,
        'results': recent_results,
    })


@login_required
@csrf_exempt
def run_backtest_view(request):
    """
    API для запуска бэктестинга стратегии.
    Принимает тип стратегии, символ, таймфрейм и параметры.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешен'}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    except Exception:
        data = request.POST

    strategy_type = data.get('strategy_type', 'RSI').upper()
    symbol = data.get('symbol', 'BTC/USDT').upper()
    timeframe = data.get('timeframe', '1h')
    period_days = int(data.get('period_days', 30))

    params = {}
    if 'rsi_period' in data:
        params['rsi_period'] = int(data['rsi_period'])
    if 'rsi_overbought' in data:
        params['rsi_overbought'] = int(data['rsi_overbought'])
    if 'rsi_oversold' in data:
        params['rsi_oversold'] = int(data['rsi_oversold'])

    try:
        result = run_backtest(
            request.user, strategy_type, symbol, timeframe, period_days, params
        )
        if result:
            messages.success(
                request,
                f'Backtest завершен! Доходность: {result.total_return}% | '
                f'Сделок: {result.total_trades} | Win Rate: {result.win_rate}%'
            )
        else:
            messages.error(request, 'Не удалось получить исторические данные')
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        messages.error(request, f'Ошибка: {str(e)}')

    return redirect('analytics:backtest')


@login_required
def leaderboard_view(request):
    """
    Страница лидерборда - рейтинг всех демо-трейдеров.
    Сортируется по общей стоимости портфеля.
    """
    accounts = DemoAccount.objects.filter(is_active=True).select_related('user')

    leaderboard = []
    for account in accounts:
        orders_filled = account.orders.filter(status='FILLED').count()
        total_volume = sum(
            o.price * o.quantity
            for o in account.orders.filter(status='FILLED')
        )

        leaderboard.append({
            'username': account.user.username,
            'total_value': account.total_value_usdt,
            'balance': account.balance,
            'total_trades': orders_filled,
            'total_volume': total_volume,
            'created_at': account.created_at,
        })

    leaderboard.sort(key=lambda x: x['total_value'], reverse=True)

    for i, entry in enumerate(leaderboard, 1):
        entry['rank'] = i

    return render(request, 'analytics/leaderboard.html', {
        'leaderboard': leaderboard,
    })


@login_required
def pnl_view(request):
    """
    Страница графика P&L (прибыли/убытков) пользователя.
    """
    snapshots = TradeSnapshot.objects.filter(user=request.user).order_by('created_at')
    account = request.user.demo_account

    chart_data = []
    for snap in snapshots:
        chart_data.append({
            'timestamp': snap.created_at.strftime('%d.%m %H:%M'),
            'value': float(snap.total_value),
        })

    initial_value = 100000.0
    current_value = float(account.total_value_usdt) if account.total_value_usdt else initial_value
    pnl = current_value - initial_value
    pnl_pct = (pnl / initial_value) * 100

    return render(request, 'analytics/pnl.html', {
        'chart_data': chart_data,
        'initial_value': initial_value,
        'current_value': current_value,
        'pnl': round(pnl, 2),
        'pnl_pct': round(pnl_pct, 2),
    })


@login_required
def export_trades_view(request):
    """
    Экспорт истории сделок в CSV.
    Скачивает файл со всеми сделками пользователя.
    """
    import csv
    from django.http import HttpResponse

    account = request.user.demo_account
    orders = DemoOrder.objects.filter(account=account).order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="trades_{request.user.username}.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Date', 'Pair', 'Side', 'Type', 'Price', 'Quantity', 'Status', 'Filled At'])

    for order in orders:
        writer.writerow([
            order.id,
            order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            order.symbol,
            order.side,
            order.order_type,
            order.price or '',
            order.quantity,
            order.status,
            order.filled_at.strftime('%Y-%m-%d %H:%M:%S') if order.filled_at else '',
        ])

    return response


@login_required
def indicators_view(request):
    """
    Страница технических индикаторов для выбранной пары.
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper()
    timeframe = request.GET.get('timeframe', '1h')

    klines = get_klines(symbol, timeframe, 200)
    if not klines:
        messages.error(request, f'Не удалось получить данные для {symbol}')
        return redirect('trading:dashboard')

    indicators = calculate_all_indicators(klines)

    current_price = float(klines[-1]['close'])

    signal = get_composite_signal(indicators, current_price)

    chart_data = {
        'timestamps': [k['timestamp'] for k in klines[-100:]],
        'closes': [float(k['close']) for k in klines[-100:]],
        'sma_20': indicators['sma_20'][-100:],
        'sma_50': indicators['sma_50'][-100:],
        'upper': indicators['bollinger']['upper'][-100:],
        'lower': indicators['bollinger']['lower'][-100:],
        'rsi': indicators['rsi'][-100:],
        'macd': indicators['macd']['macd'][-100:],
        'macd_signal': indicators['macd']['signal'][-100:],
        'macd_histogram': indicators['bollinger']['middle'][-100:],
    }

    return render(request, 'analytics/indicators.html', {
        'symbol': symbol,
        'timeframe': timeframe,
        'indicators': indicators,
        'signal': signal,
        'current_price': current_price,
        'chart_data': json.dumps(chart_data),
    })
