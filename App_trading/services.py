from decimal import Decimal
from django.db import transaction
from django.utils.timezone import now
from App_users.models import DemoOrder, DemoAccount
from App_market.services import get_ticker
import logging

logger = logging.getLogger(__name__)


def execute_market_order(account, symbol, side, quantity):
    """
    Исполняет рыночный ордер мгновенно
    """
    ticker = get_ticker(symbol)
    if not ticker:
        raise ValueError(f"Не удалось получить цену для {symbol}")
    
    price = ticker['price']
    total = price * Decimal(str(quantity))
    asset = symbol.split('/')[0]
    
    with transaction.atomic():
        # Проверяем и обновляем баланс
        if side == 'BUY':
            if account.get_balance('USDT') < total:
                raise ValueError(
                    f"Недостаточно USDT. Баланс: {account.get_balance('USDT'):.2f}, нужно: {total:.2f}"
                )
            account.update_balance('USDT', -total)
            account.update_balance(asset, quantity)
        else:
            if account.get_balance(asset) < quantity:
                raise ValueError(
                    f"Недостаточно {asset}. Баланс: {account.get_balance(asset):.8f}, нужно: {quantity:.8f}"
                )
            account.update_balance(asset, -quantity)
            account.update_balance('USDT', total)
        
        # Создаем ордер
        order = DemoOrder.objects.create(
            account=account,
            symbol=symbol,
            side=side,
            order_type='MARKET',
            price=price,
            quantity=quantity,
            filled_quantity=quantity,
            status='FILLED',
            filled_at=now()
        )
        
        # Обновляем общую стоимость портфеля
        tickers = get_all_tickers_for_balance(account)
        account.calculate_total_value(tickers)
        
        logger.info(f"✅ Рыночный ордер исполнен: {order}")
        return order


def execute_limit_order(account, symbol, side, quantity, price):
    """
    Создает лимитный ордер (ждет исполнения)
    """
    asset = symbol.split('/')[0]
    total = price * Decimal(str(quantity))
    
    with transaction.atomic():
        if side == 'BUY':
            if account.get_balance('USDT') < total:
                raise ValueError(
                    f"Недостаточно USDT. Баланс: {account.get_balance('USDT'):.2f}, нужно: {total:.2f}"
                )
            # Резервируем USDT
            account.update_balance('USDT', -total)
        else:
            if account.get_balance(asset) < quantity:
                raise ValueError(
                    f"Недостаточно {asset}. Баланс: {account.get_balance(asset):.8f}, нужно: {quantity:.8f}"
                )
            # Резервируем актив
            account.update_balance(asset, -quantity)
        
        # Создаем открытый ордер
        order = DemoOrder.objects.create(
            account=account,
            symbol=symbol,
            side=side,
            order_type='LIMIT',
            price=price,
            quantity=quantity,
            status='OPEN'
        )
        
        logger.info(f"📝 Лимитный ордер создан: {order}")
        return order


def cancel_order(order_id):
    """
    Отмена лимитного ордера с возвратом средств
    """
    order = DemoOrder.objects.get(id=order_id)
    
    if order.status != 'OPEN':
        raise ValueError(f"Нельзя отменить ордер в статусе {order.status}")
    
    with transaction.atomic():
        account = order.account
        asset = order.symbol.split('/')[0]
        
        if order.side == 'BUY':
            # Возвращаем зарезервированные USDT
            total = order.price * order.quantity
            account.update_balance('USDT', total)
        else:
            # Возвращаем зарезервированный актив
            account.update_balance(asset, order.quantity)
        
        order.status = 'CANCELLED'
        order.save()
        
        logger.info(f"❌ Ордер отменен: {order}")
        return order


def get_all_tickers_for_balance(account):
    """
    Получает цены всех активов в портфеле
    """
    from App_market.services import get_ticker
    
    assets = [asset for asset in account.balance.keys() if asset != 'USDT']
    result = {}
    
    for asset in assets:
        ticker = get_ticker(f"{asset}/USDT")
        if ticker:
            result[asset] = ticker['price']
    
    return result


def check_and_fill_limit_orders(symbol):
    """
    Проверяет и исполняет лимитные ордера по цене
    (Запускается по расписанию)
    """
    ticker = get_ticker(symbol)
    if not ticker:
        return
    
    current_price = ticker['price']
    
    # Находим открытые ордера по этой паре
    orders = DemoOrder.objects.filter(
        symbol=symbol,
        status='OPEN'
    )
    
    filled = 0
    
    for order in orders:
        should_fill = False
        
        if order.side == 'BUY' and order.price >= current_price:
            should_fill = True
        elif order.side == 'SELL' and order.price <= current_price:
            should_fill = True
        
        if should_fill:
            with transaction.atomic():
                asset = order.symbol.split('/')[0]
                
                if order.side == 'BUY':
                    order.account.update_balance(asset, order.quantity)
                else:
                    total = order.price * order.quantity
                    order.account.update_balance('USDT', total)
                
                order.status = 'FILLED'
                order.filled_quantity = order.quantity
                order.filled_at = now()
                order.price = current_price
                order.save()
                
                filled += 1
                logger.info(f"✅ Лимитный ордер исполнен: {order}")
    
    return filled