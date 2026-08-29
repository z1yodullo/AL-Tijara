from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.timezone import now
from App_users.models import DemoOrder
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=DemoOrder)
def validate_order_before_save(sender, instance, **kwargs):
    """
    Проверка ордера перед сохранением
    """
    if instance.quantity <= 0:
        raise ValueError("Количество должно быть больше 0")
    
    if instance.order_type == 'LIMIT' and not instance.price:
        raise ValueError("Для лимитного ордера нужна цена")
    
    if instance.price and instance.price <= 0:
        raise ValueError("Цена должна быть больше 0")


@receiver(post_save, sender=DemoOrder)
def log_order_creation(sender, instance, created, **kwargs):
    """
    Логирование создания и изменения ордера
    """
    if created:
        logger.info(f"📝 Новый ордер: {instance}")
    else:
        # Проверяем, изменился ли статус
        if instance.pk:
            old = sender.objects.get(pk=instance.pk)
            if old.status != instance.status:
                logger.info(f"🔄 Статус ордера изменен: {old.id} | {old.status} → {instance.status}")


@receiver(post_save, sender=DemoOrder)
def update_account_value_on_order(sender, instance, created, **kwargs):
    """
    Обновление общей стоимости портфеля при исполнении ордера
    """
    if instance.status == 'FILLED' and (created or instance.filled_at is None):
        from App_market.services import get_ticker
        
        account = instance.account
        ticker = get_ticker(instance.symbol)
        
        if ticker:
            # Обновляем общую стоимость портфеля
            prices = {instance.symbol.split('/')[0]: ticker['price']}
            account.calculate_total_value(prices)
            logger.debug(f"💼 Обновлена стоимость портфеля для {account.user.username}")