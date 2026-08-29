from django.core.management.base import BaseCommand
from App_analytics.services import check_alerts
from App_trading.stop_loss import check_stop_loss_take_profit
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Команда для проверки ценовых алертов и стоп-лосс/тейк-профит ордеров.
    Запуск: python manage.py check_triggers
    """

    help = 'Проверяет алерты и стоп-лосс/тейк-профит ордера'

    def handle(self, *args, **options):
        """
        Запускает проверку алертов и автоматическое исполнение стоп-лосс/тейк-профит.
        """
        alerts_triggered = check_alerts()
        self.stdout.write(
            self.style.SUCCESS(f'Сработало алертов: {alerts_triggered}')
        )

        sl_tp_executed = check_stop_loss_take_profit()
        self.stdout.write(
            self.style.SUCCESS(f'Исполнено стоп-лосс/тейк-профит: {sl_tp_executed}')
        )

        logger.info(f'Triggers checked: alerts={alerts_triggered}, sl_tp={sl_tp_executed}')
