from django.contrib import admin
from .models import DemoAccount, DemoOrder


@admin.register(DemoAccount)
class DemoAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_value_usdt', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    fields = ['user', 'balance', 'total_value_usdt', 'is_active', 'created_at', 'updated_at']


@admin.register(DemoOrder)
class DemoOrderAdmin(admin.ModelAdmin):
    list_display = ['account', 'symbol', 'side', 'order_type', 'quantity', 'status', 'created_at']
    list_filter = ['status', 'side', 'order_type', 'symbol']
    search_fields = ['account__user__username', 'symbol']
    readonly_fields = ['created_at', 'filled_at']
    fields = [
        'account', 'symbol', 'side', 'order_type', 
        'price', 'quantity', 'filled_quantity', 
        'status', 'error_message', 'created_at', 'filled_at'
    ]