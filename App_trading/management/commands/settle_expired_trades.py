from django.core.management.base import BaseCommand
from App_users.models import DemoOrder
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Закрывает все бинарные сделки с истёкшим expiration_time'

    def handle(self, *args, **options):
        settled = DemoOrder.settle_expired_trades()
        if settled:
            self.stdout.write(self.style.SUCCESS(f'Settled {settled} expired trades'))
        else:
            self.stdout.write('No expired trades to settle')
