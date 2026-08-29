import logging
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import DemoAccount, RealAccount
from django.conf import settings

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_demo_account(sender, instance, created, **kwargs):
    """
    При создании нового пользователя автоматически создаем демо-счет и реальный счет
    """
    if created:
        DemoAccount.objects.create(
            user=instance,
            balance=getattr(settings, 'DEMO_STARTING_BALANCE', {
                'USDT': 100000.0,
                'BTC': 0.0,
                'ETH': 0.0,
                'BNB': 0.0,
                'SOL': 0.0,
            })
        )
        RealAccount.objects.create(
            user=instance,
            balance={'USDT': 0.0, 'BTC': 0.0, 'ETH': 0.0, 'BNB': 0.0}
        )
        logger.info(f"✅ Демо-счет и реальный счет созданы для {instance.username}")


@receiver(post_save, sender=User)
def save_demo_account(sender, instance, **kwargs):
    """
    При сохранении пользователя сохраняем его счета
    """
    if hasattr(instance, 'demo_account'):
        try:
            instance.demo_account.save()
            logger.debug(f"Демо-счет сохранен для {instance.username}")
        except Exception as e:
            logger.error(f"Ошибка сохранения демо-счета для {instance.username}: {e}")

    if hasattr(instance, 'real_account'):
        try:
            instance.real_account.save()
            logger.debug(f"Реальный счет сохранен для {instance.username}")
        except Exception as e:
            logger.error(f"Ошибка сохранения реального счета для {instance.username}: {e}")