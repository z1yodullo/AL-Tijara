from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)


class GuestAccessMiddleware:
    """
    Проверяет доступ для неавторизованных пользователей
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Страницы, доступные без авторизации
        self.public_urls = [
            '/login/',
            '/register/',
            '/admin/',
            '/api/price/',
            '/api/live-price/',
            '/api/prices/',
            '/api/orderbook/',
            '/api/klines/',
        ]
    
    def __call__(self, request):
        # Проверяем, нужно ли защищать страницу
        if not request.user.is_authenticated:
            for url in self.public_urls:
                if request.path.startswith(url):
                    break
            else:
                # Сохраняем URL для редиректа после входа
                request.session['next_url'] = request.path
                messages.warning(request, 'Пожалуйста, войдите для доступа к этой странице')
                return redirect('users:login')
        
        response = self.get_response(request)
        return response


class UserActivityMiddleware:
    """
    Логирование активности пользователей
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Обновляем время активности
            request.session['last_activity'] = str(django.utils.timezone.now())
            
            # Логируем запросы (только POST)
            if request.method == 'POST' and not request.path.startswith('/admin/'):
                logger.info(
                    f"ACTIVITY: {request.user.username} | {request.method} {request.path}"
                )
        
        response = self.get_response(request)
        return response


class DemoModeMiddleware:
    """
    Проверяет демо-режим и добавляет счет в запрос
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                # Проверяем наличие демо-счета
                if hasattr(request.user, 'demo_account'):
                    request.demo_account = request.user.demo_account
                else:
                    from App_users.models import DemoAccount
                    from django.conf import settings
                    request.demo_account = DemoAccount.objects.create(
                        user=request.user,
                        balance=settings.DEMO_STARTING_BALANCE
                    )
                    logger.info(f"Демо-счет создан для {request.user.username}")
            except Exception as e:
                logger.error(f"Ошибка демо-счета для {request.user.username}: {e}")
        
        response = self.get_response(request)
        return response