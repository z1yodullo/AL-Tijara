from django.core.management.base import BaseCommand
from django.utils.timezone import now
from App_trading.services import check_and_fill_limit_orders
from App_market.services import get_all_tickers
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Проверяет и исполняет лимитные ордера по текущим ценам'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Проверить только конкретную пару (например BTC/USDT)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('🔄 Начинаем проверку лимитных ордеров...')
        
        try:
            if options.get('symbol'):
                symbols = [options['symbol']]
            else:
                # Получаем все активные пары
                tickers = get_all_tickers()
                symbols = [t['symbol'] for t in tickers]
            
            total_filled = 0
            
            for symbol in symbols:
                filled = check_and_fill_limit_orders(symbol)
                total_filled += filled
                
                if filled > 0:
                    self.stdout.write(f'✅ {symbol}: исполнено {filled} ордеров')
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Готово! Исполнено ордеров: {total_filled}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка: {e}')
            )
            logger.error(f"Ошибка проверки ордеров: {e}")