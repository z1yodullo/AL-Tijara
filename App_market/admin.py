from django.contrib import admin
try:
    from .models import PriceHistory, Symbol
    
    @admin.register(Symbol)
    class SymbolAdmin(admin.ModelAdmin):
        list_display = ['symbol', 'base_asset', 'quote_asset', 'is_active', 'created_at']
        list_filter = ['is_active', 'quote_asset']
        search_fields = ['symbol', 'base_asset']
        readonly_fields = ['created_at', 'updated_at']

    @admin.register(PriceHistory)
    class PriceHistoryAdmin(admin.ModelAdmin):
        list_display = ['symbol', 'price', 'volume', 'timestamp']
        list_filter = ['symbol', 'timestamp']
        search_fields = ['symbol__symbol']
        readonly_fields = ['timestamp']
        date_hierarchy = 'timestamp'

except ImportError:
    pass