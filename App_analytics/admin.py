from django.contrib import admin
from .models import TradingStats, PriceAlert


@admin.register(TradingStats)
class TradingStatsAdmin(admin.ModelAdmin):
    list_display = ['account', 'total_trades', 'total_volume', 'win_rate', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'account', 
        'total_trades', 'total_volume', 'total_profit',
        'win_rate', 'profit_factor', 'sharpe_ratio',
        'best_trade', 'worst_trade', 'avg_trade_profit',
        'created_at', 'updated_at'
    ]


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'symbol', 'target_price', 'direction', 'is_triggered', 'created_at']
    list_filter = ['is_triggered', 'direction', 'symbol']
    search_fields = ['user__username', 'symbol']
    readonly_fields = ['triggered_at', 'created_at']