from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('trading:dashboard') if request.user.is_authenticated else redirect('users:login'), name='home'),
    path('', include('App_users.urls')),   
    path('', include('App_market.urls')),    
    path('', include('App_trading.urls')),
    path('', include('App_analytics.urls')),
]