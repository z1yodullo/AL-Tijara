from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
import logging
import threading

logger = logging.getLogger(__name__)


class DemoAccount(models.Model):
    """
    Демо-счет пользователя
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='demo_account',
        verbose_name='Пользователь'
    )
    balance = models.JSONField(
        default=dict,
        verbose_name='Баланс',
        help_text='{"USDT": 100000.0, "BTC": 0.0}'
    )
    total_value_usdt = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0,
        verbose_name='Общая стоимость (USDT)',
        help_text="Общая стоимость портфеля в USDT"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text="Можно ли использовать демо-счет"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создан'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлен'
    )

    class Meta:
        verbose_name = 'Демо-счет'
        verbose_name_plural = 'Демо-счета'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - Демо счет"

    def get_balance(self, asset='USDT'):
        """
        Получить баланс по активу
        """
        return Decimal(str(self.balance.get(asset, 0)))

    def update_balance(self, asset, amount):
        """
        Обновить баланс (атомарно через F-выражения)
        """
        from django.db.models import F

        if Decimal(str(amount)) < 0:
            current = self.get_balance(asset)
            if current + Decimal(str(amount)) < 0:
                raise ValueError(f"Недостаточно {asset}. Баланс: {current}, запрошено: {amount}")

        self.refresh_from_db()
        current_balance = self.get_balance(asset)
        new_balance = float(current_balance + Decimal(str(amount)))
        if new_balance < 0:
            raise ValueError(f"Недостаточно {asset}. Баланс: {current_balance}, запрошено: {amount}")

        self.balance[asset] = new_balance
        self.save(update_fields=['balance', 'updated_at'])

        logger.info(f"Баланс обновлен: {self.user.username} | {asset}: {current_balance} → {new_balance}")
        return Decimal(str(new_balance))

    def calculate_total_value(self, prices):
        """
        Рассчитать общую стоимость портфеля
        prices: {'BTC': 45000.0, 'ETH': 3000.0}
        """
        total = Decimal(str(self.balance.get('USDT', 0)))
        
        for asset, amount in self.balance.items():
            if asset != 'USDT' and asset in prices:
                total += Decimal(str(amount)) * Decimal(str(prices[asset]))
        
        self.total_value_usdt = total
        self.save()
        return total


class DemoOrder(models.Model):
    """
    Демо-ордер
    """
    SIDE_CHOICES = [
        ('BUY', 'Покупка'),
        ('SELL', 'Продажа'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Открыт'),
        ('FILLED', 'Исполнен'),
        ('CANCELLED', 'Отменен'),
        ('REJECTED', 'Отклонен'),
    ]
    
    ORDER_TYPE_CHOICES = [
        ('MARKET', 'Рыночный'),
        ('LIMIT', 'Лимитный'),
    ]
    
    account = models.ForeignKey(
        DemoAccount, 
        on_delete=models.CASCADE, 
        related_name='orders',
        verbose_name='Счет'
    )
    symbol = models.CharField(
        max_length=20, 
        verbose_name='Торговая пара',
        help_text="Например BTC/USDT"
    )
    side = models.CharField(
        max_length=4, 
        choices=SIDE_CHOICES,
        verbose_name='Сторона'
    )
    order_type = models.CharField(
        max_length=10, 
        default='MARKET', 
        choices=ORDER_TYPE_CHOICES,
        verbose_name='Тип ордера'
    )
    price = models.DecimalField(
        max_digits=20, 
        decimal_places=8, 
        null=True, 
        blank=True,
        verbose_name='Цена',
        help_text="Для лимитных ордеров"
    )
    quantity = models.DecimalField(
        max_digits=20, 
        decimal_places=8,
        validators=[MinValueValidator(Decimal('0.000001'))],
        verbose_name='Количество'
    )
    filled_quantity = models.DecimalField(
        max_digits=20, 
        decimal_places=8, 
        default=0,
        verbose_name='Исполнено'
    )
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='OPEN',
        verbose_name='Статус'
    )
    error_message = models.TextField(
        blank=True, 
        null=True,
        verbose_name='Ошибка'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создан'
    )
    filled_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Исполнен'
    )

    class Meta:
        verbose_name = 'Демо-ордер'
        verbose_name_plural = 'Демо-ордера'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.account.user.username} | {self.side} {self.quantity} {self.symbol}"

    def get_total(self):
        """Общая сумма ордера"""
        if self.price:
            return self.price * self.quantity
        return Decimal('0')

    def get_remaining(self):
        """Оставшееся количество"""
        return self.quantity - self.filled_quantity

    def fill(self, price=None):
        """Исполнить ордер"""
        if self.status != 'OPEN':
            raise ValueError(f"Ордер уже {self.status}")
        
        self.status = 'FILLED'
        self.filled_quantity = self.quantity
        if price:
            self.price = price
        self.filled_at = self.get_current_time()
        self.save()
        
        logger.info(f"Ордер исполнен: {self}")
        return self

    def cancel(self):
        """Отменить ордер"""
        if self.status != 'OPEN':
            raise ValueError(f"Нельзя отменить ордер в статусе {self.status}")
        
        self.status = 'CANCELLED'
        self.save()
        logger.info(f"Ордер отменен: {self}")
        return self

    stop_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='Stop Loss',
        help_text="Цена стоп-лосс"
    )
    take_profit = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='Take Profit',
        help_text="Цена тейк-профит"
    )

    trade_duration = models.IntegerField(
        default=0,
        verbose_name='Длительность сделки (сек)',
        help_text="Длительность бинарной сделки в секундах"
    )
    trade_direction = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        choices=[('CALL', 'Вверх'), ('PUT', 'Вниз')],
        verbose_name='Направление сделки'
    )
    entry_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='Цена входа'
    )
    expiration_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время экспирации',
        help_text="Когда сделка должна быть закрыта"
    )

    def get_current_time(self):
        """Возвращает текущее время для filled_at"""
        from django.utils.timezone import now
        return now()

    @classmethod
    def settle_expired_trades(cls):
        """
        Закрывает все бинарные сделки, у которых истёк expiration_time.
        Также закрывает orphan-сделки без expiration_time старше 24 часов.
        Вызывается из management command или periodic task.
        """
        from django.utils.timezone import now, timedelta
        from App_market.services import get_ticker

        now_time = now()

        expired = cls.objects.filter(
            status='OPEN',
            trade_direction__isnull=False,
            expiration_time__lte=now_time
        ).select_related('account')

        orphans = cls.objects.filter(
            status='OPEN',
            trade_direction__isnull=False,
            expiration_time__isnull=True,
            created_at__lt=now_time - timedelta(hours=1)
        ).select_related('account')

        orders_to_settle = list(expired) + list(orphans)

        settled_count = 0
        for order in orders_to_settle:
            try:
                order.refresh_from_db()
                if order.status != 'OPEN':
                    continue

                ticker = get_ticker(order.symbol)
                if not ticker or not order.entry_price or not order.trade_direction:
                    order.status = 'CANCELLED'
                    order.error_message = 'SETTLE_REFUND - data missing'
                    order.filled_at = now_time
                    order.save(update_fields=['status', 'error_message', 'filled_at'])
                    order.account.update_balance('USDT', order.quantity)
                    settled_count += 1
                    continue

                exit_price = float(ticker['price'])
                entry = float(order.entry_price)
                direction = order.trade_direction
                amount = float(order.quantity)

                is_win = (direction == 'CALL' and exit_price > entry) or \
                         (direction == 'PUT' and exit_price < entry)

                if exit_price == entry:
                    is_win = False

                profit_pct = 87
                if is_win:
                    payout = amount * (1 + profit_pct / 100)
                    order.account.update_balance('USDT', Decimal(str(payout)))
                    order.status = 'FILLED'
                    order.error_message = f'WIN +${payout:.2f}'
                else:
                    order.status = 'CANCELLED'
                    order.error_message = f'LOST -${amount:.2f}'

                order.filled_at = now_time
                order.save(update_fields=['status', 'error_message', 'filled_at'])
                settled_count += 1

                logger.info(f"Settled trade #{order.id}: {order.error_message}")

            except Exception as e:
                logger.error(f"Settle error for order #{order.id}: {e}")
                try:
                    order.refresh_from_db()
                    if order.status == 'OPEN':
                        order.account.update_balance('USDT', order.quantity)
                        order.status = 'CANCELLED'
                        order.error_message = f'SETTLE_ERROR - refunded'
                        order.filled_at = now_time
                        order.save(update_fields=['status', 'error_message', 'filled_at'])
                        settled_count += 1
                except Exception:
                    logger.error(f"Refund also failed for order #{order.id}")

        return settled_count


class RealAccount(models.Model):
    """
    Реальный счёт пользователя
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='real_account',
        verbose_name='Пользователь'
    )
    balance = models.JSONField(
        default=dict,
        verbose_name='Баланс',
        help_text='{"USDT": 0.0, "BTC": 0.0}'
    )
    total_value_usdt = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name='Общая стоимость (USDT)',
        help_text="Общая стоимость портфеля в USDT"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text="Можно ли использовать реальный счёт"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создан'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлен'
    )

    class Meta:
        verbose_name = 'Реальный счёт'
        verbose_name_plural = 'Реальные счета'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - Реальный счет"

    def get_balance(self, asset='USDT'):
        return Decimal(str(self.balance.get(asset, 0)))

    def update_balance(self, asset, amount):
        current = self.get_balance(asset)
        new_balance = current + Decimal(str(amount))

        if new_balance < 0:
            raise ValueError(f"Недостаточно {asset}. Баланс: {current}, запрошено: {amount}")

        self.balance[asset] = float(new_balance)
        self.save(update_fields=['balance', 'updated_at'])

        logger.info(f"Баланс обновлен (реальный): {self.user.username} | {asset}: {current} → {new_balance}")
        return new_balance

    def calculate_total_value(self, prices):
        total = Decimal(str(self.balance.get('USDT', 0)))

        for asset, amount in self.balance.items():
            if asset != 'USDT' and asset in prices:
                total += Decimal(str(amount)) * Decimal(str(prices[asset]))

        self.total_value_usdt = total
        self.save()
        return total


class Watchlist(models.Model):
    """
    Список отслеживаемых торговых пар пользователя
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='watchlist',
        verbose_name='Пользователь'
    )
    symbol = models.CharField(
        max_length=20,
        verbose_name='Торговая пара',
        help_text="Например BTC/USDT"
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Добавлен'
    )

    class Meta:
        verbose_name = 'Список отслеживания'
        verbose_name_plural = 'Списки отслеживания'
        unique_together = ['user', 'symbol']

    def __str__(self):
        return f"{self.user.username} → {self.symbol}"