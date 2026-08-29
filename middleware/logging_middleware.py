import logging
import json
from django.utils.timezone import now

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    """
    Логирует все запросы пользователей для анализа и отладки.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Логируем начало запроса
        start_time = now()
        
        response = self.get_response(request)
        
        # Логируем результат
        duration = (now() - start_time).total_seconds()
        
        log_data = {
            'user': request.user.username if request.user.is_authenticated else 'Guest',
            'path': request.path,
            'method': request.method,
            'status_code': response.status_code,
            'duration': f"{duration:.4f}s",
            'ip': request.META.get('REMOTE_ADDR'),
        }
        
        logger.info(json.dumps(log_data))
        return response