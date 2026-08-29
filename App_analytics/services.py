from django.utils.timezone import now
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def check_alerts():
    """
    Проверяет все активные ценовые алерты и срабатывает при достижении целевой цены.
    Запускается по расписанию (каждую минуту).
    """
    from App_analytics.models import PriceAlert
    from App_market.services import get_ticker

    alerts = PriceAlert.objects.filter(is_triggered=False)
    triggered_count = 0

    for alert in alerts:
        ticker = get_ticker(alert.symbol)
        if not ticker:
            continue

        current_price = ticker['price']
        should_trigger = False

        if alert.direction == 'ABOVE' and current_price >= alert.target_price:
            should_trigger = True
        elif alert.direction == 'BELOW' and current_price <= alert.target_price:
            should_trigger = True

        if should_trigger:
            alert.is_triggered = True
            alert.triggered_at = now()
            alert.save()
            triggered_count += 1
            logger.info(
                f"Alert triggered: {alert.user.username} | "
                f"{alert.symbol} {alert.direction} {alert.target_price} "
                f"(current: {current_price})"
            )

    return triggered_count


def create_alert(user, symbol, target_price, direction):
    """
    Создает новый ценовой алерт для пользователя.
    Возвращает созданный объект PriceAlert.
    """
    from App_analytics.models import PriceAlert

    alert = PriceAlert.objects.create(
        user=user,
        symbol=symbol.upper(),
        target_price=Decimal(str(target_price)),
        direction=direction.upper()
    )
    logger.info(f"Alert created: {user.username} | {symbol} {direction} {target_price}")
    return alert


def delete_alert(user, alert_id):
    """
    Удаляет ценовой алерт пользователя.
    Проверяет принадлежность алерта перед удалением.
    """
    from App_analytics.models import PriceAlert

    alert = PriceAlert.objects.get(id=alert_id, user=user)
    alert.delete()
    logger.info(f"Alert deleted: {user.username} | {alert_id}")
    return True
