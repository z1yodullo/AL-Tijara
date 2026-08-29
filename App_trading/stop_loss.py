from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def check_stop_loss_take_profit():
    """
    Проверяет все открытые ордера с установленными стоп-лосс и тейк-профит.
    Автоматически исполняет рыночный ордер при достижении целевой цены.
    Запускается по расписанию.
    """
    from App_users.models import DemoOrder
    from App_market.services import get_ticker
    from App_trading.services import execute_market_order

    orders = DemoOrder.objects.filter(
        status='OPEN',
        order_type='LIMIT'
    ).exclude(stop_loss__isnull=True, take_profit__isnull=True)

    executed = 0

    for order in orders:
        ticker = get_ticker(order.symbol)
        if not ticker:
            continue

        current_price = ticker['price']
        should_execute = False
        execute_side = None

        if order.side == 'BUY':
            if order.take_profit and current_price >= order.take_profit:
                should_execute = True
                execute_side = 'SELL'
            elif order.stop_loss and current_price <= order.stop_loss:
                should_execute = True
                execute_side = 'SELL'
        else:
            if order.take_profit and current_price <= order.take_profit:
                should_execute = True
                execute_side = 'BUY'
            elif order.stop_loss and current_price >= order.stop_loss:
                should_execute = True
                execute_side = 'BUY'

        if should_execute and execute_side:
            try:
                asset = order.symbol.split('/')[0]
                quantity = order.quantity

                if execute_side == 'BUY':
                    total = current_price * quantity
                    if order.account.get_balance('USDT') >= total:
                        execute_market_order(order.account, order.symbol, execute_side, quantity)
                        order.status = 'CANCELLED'
                        order.save()
                        executed += 1
                        logger.info(
                            f"Stop/TP executed: {order.account.user.username} | "
                            f"{order.symbol} {execute_side} at {current_price}"
                        )
                else:
                    if order.account.get_balance(asset) >= quantity:
                        execute_market_order(order.account, order.symbol, execute_side, quantity)
                        order.status = 'CANCELLED'
                        order.save()
                        executed += 1
                        logger.info(
                            f"Stop/TP executed: {order.account.user.username} | "
                            f"{order.symbol} {execute_side} at {current_price}"
                        )
            except Exception as e:
                logger.error(f"Error executing stop/TP for order {order.id}: {e}")

    return executed


def set_stop_loss_take_profit(order_id, user, stop_loss=None, take_profit=None):
    """
    Устанавливает стоп-лосс и/или тейк-профит для лимитного ордера.
    Принимает ID ордера, пользователя и целевые цены.
    """
    from App_users.models import DemoOrder

    order = DemoOrder.objects.get(id=order_id, account__user=user)

    if order.status != 'OPEN':
        raise ValueError(f"Ордер уже {order.status}")

    if stop_loss is not None:
        order.stop_loss = Decimal(str(stop_loss))
    if take_profit is not None:
        order.take_profit = Decimal(str(take_profit))

    order.save()
    logger.info(
        f"Stop/TP set: {user.username} | Order {order_id} | "
        f"SL={stop_loss} TP={take_profit}"
    )
    return order
