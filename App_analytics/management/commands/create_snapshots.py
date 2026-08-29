from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from App_analytics.models import TradeSnapshot
from App_market.services import get_all_tickers_for_balance
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Команда для создания снимков портфеля всех активных пользователей.
    Используется для построения графиков P&L.
    Запуск: python manage.py create_snapshots
    """

    help = 'Создает снимки портфеля для графиков P&L'

    def handle(self, *args, **options):
        """
        Основная логика команды.
        Проходит по всем пользователям с демо-счетами и сохраняет текущее состояние портфеля.
        """
        users = User.objects.filter(is_active=True)
        created_count = 0

        for user in users:
            try:
                account = user.demo_account
            except Exception:
                continue

            prices = get_all_tickers_for_balance(account)
            account.calculate_total_value(prices)

            TradeSnapshot.objects.create(
                user=user,
                total_value=account.total_value_usdt,
                balance=account.balance,
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Создано снимков: {created_count}')
        )
        logger.info(f'Snapshots created: {created_count}')
