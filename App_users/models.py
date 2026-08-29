from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
import logging

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
        Обновить баланс
        """
        current = self.get_balance(asset)
        new_balance = current + Decimal(str(amount))
        
        if new_balance < 0:
            raise ValueError(f"Недостаточно {asset}. Баланс: {current}, запрошено: {amount}")
        
        self.balance[asset] = float(new_balance)
        self.save()
        
        logger.info(f"Баланс обновлен: {self.user.username} | {asset}: {current} → {new_balance}")
        return new_balance

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

    def get_current_time(self):
        """Возвращает текущее время для filled_at"""
        from django.utils.timezone import now
        return now()


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
        self.save()

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