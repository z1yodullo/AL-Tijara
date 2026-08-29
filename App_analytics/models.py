from django.db import models
from django.contrib.auth.models import User
from App_users.models import DemoAccount
from decimal import Decimal


class TradingStats(models.Model):
    """
    Статистика торговли пользователя
    """
    account = models.OneToOneField(
        DemoAccount, 
        on_delete=models.CASCADE, 
        related_name='stats'
    )
    
    # Общая статистика
    total_trades = models.IntegerField(default=0, verbose_name='Всего сделок')
    total_volume = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0,
        verbose_name='Общий объем (USDT)'
    )
    total_profit = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0,
        verbose_name='Общая прибыль (USDT)'
    )
    
    # Процентные показатели
    win_rate = models.FloatField(default=0.0, verbose_name='Процент побед')
    profit_factor = models.FloatField(default=0.0, verbose_name='Фактор прибыли')
    sharpe_ratio = models.FloatField(default=0.0, verbose_name='Коэффициент Шарпа')
    
    # Лучшие и худшие сделки
    best_trade = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0,
        verbose_name='Лучшая сделка (USDT)'
    )
    worst_trade = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0,
        verbose_name='Худшая сделка (USDT)'
    )
    avg_trade_profit = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0,
        verbose_name='Средняя прибыль (USDT)'
    )
    
    # Временные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Статистика торговли'
        verbose_name_plural = 'Статистика торговли'
    
    def __str__(self):
        return f"Статистика {self.account.user.username}"
    
    def calculate_stats(self):
        """
        Пересчет статистики на основе ордеров
        """
        from django.db.models import Sum, Count, Avg
        
        orders = self.account.orders.filter(status='FILLED')
        
        if not orders.exists():
            return
        
        # Общее количество сделок
        self.total_trades = orders.count()
        
        # Общий объем
        total_volume = Decimal('0')
        total_profit = Decimal('0')
        best = Decimal('0')
        worst = Decimal('0')
        wins = 0
        
        for order in orders:
            volume = order.price * order.quantity
            total_volume += volume
            
            # Расчет прибыли (упрощенный)
            if order.side == 'BUY':
                # Условно считаем прибыль после продажи
                pass
            else:
                # Условно считаем прибыль при продаже
                pass
        
        self.total_volume = total_volume
        self.total_profit = total_profit
        
        # Процент побед
        if self.total_trades > 0:
            self.win_rate = (wins / self.total_trades) * 100
        
        self.save()
        return self


class PriceAlert(models.Model):
    """
    Уведомления о достижении цены
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    symbol = models.CharField(max_length=20)
    target_price = models.DecimalField(max_digits=20, decimal_places=8)
    direction = models.CharField(max_length=10, choices=[
        ('ABOVE', 'Выше'),
        ('BELOW', 'Ниже'),
    ])
    is_triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Ценовое уведомление'
        verbose_name_plural = 'Ценовые уведомления'
    
    def __str__(self):
        return f"{self.user.username} | {self.symbol} {'↑' if self.direction == 'ABOVE' else '↓'} ${self.target_price}"


class BacktestStrategy(models.Model):
    """
    Сохраненная стратегия для бэктестинга
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='strategies',
        verbose_name='Пользователь'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название стратегии'
    )
    symbol = models.CharField(
        max_length=20,
        verbose_name='Торговая пара'
    )
    strategy_type = models.CharField(
        max_length=20,
        choices=[
            ('RSI', 'RSI'),
            ('MACD', 'MACD'),
            ('BOLLINGER', 'Bollinger Bands'),
            ('COMPOSITE', 'Композитная'),
        ],
        verbose_name='Тип стратегии'
    )
    params = models.JSONField(
        default=dict,
        verbose_name='Параметры стратегии',
        help_text='JSON с параметрами (period, threshold и т.д.)'
    )
    timeframe = models.CharField(
        max_length=10,
        default='1h',
        verbose_name='Таймфрейм'
    )
    period_days = models.IntegerField(
        default=30,
        verbose_name='Период (дней)'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Стратегия для бэктестинга'
        verbose_name_plural = 'Стратегии для бэктестинга'

    def __str__(self):
        return f"{self.name} ({self.strategy_type} {self.symbol})"


class BacktestResult(models.Model):
    """
    Результат бэктестинга стратегии
    """
    strategy = models.ForeignKey(
        BacktestStrategy,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='Стратегия'
    )
    total_trades = models.IntegerField(default=0, verbose_name='Всего сделок')
    winning_trades = models.IntegerField(default=0, verbose_name='Прибыльных')
    losing_trades = models.IntegerField(default=0, verbose_name='Убыточных')
    total_return = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Общая доходность (%)'
    )
    max_drawdown = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Максимальная просадка (%)'
    )
    sharpe_ratio = models.FloatField(default=0, verbose_name='Коэффициент Шарпа')
    win_rate = models.FloatField(default=0, verbose_name='Процент побед')
    equity_curve = models.JSONField(
        default=list,
        verbose_name='Кривая эквити'
    )
    trades_log = models.JSONField(
        default=list,
        verbose_name='Журнал сделок'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Результат бэктестинга'
        verbose_name_plural = 'Результаты бэктестинга'

    def __str__(self):
        return f"{self.strategy.name} | Return: {self.total_return}%"


class TradeSnapshot(models.Model):
    """
    Снимок состояния портфеля для построения графика P&L
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='snapshots',
        verbose_name='Пользователь'
    )
    total_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name='Общая стоимость портфеля'
    )
    balance = models.JSONField(
        default=dict,
        verbose_name='Баланс на момент снимка'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Снимок портфеля'
        verbose_name_plural = 'Снимки портфеля'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.total_value} USDT | {self.created_at}"