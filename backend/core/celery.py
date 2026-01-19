import os
from celery import Celery
from django.conf import settings

# Установка переменной окружения для настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Использование строки настроек из настроек Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение задач в приложениях Django
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Конфигурация Celery
app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Europe/Moscow',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)

# Очереди задач
app.conf.task_routes = {
    'accounts.tasks.check_account_task': {'queue': 'telegram_check'},
    'accounts.tasks.bulk_check_accounts_task': {'queue': 'telegram_bulk'},
    'accounts.tasks.reauthorize_account_task': {'queue': 'telegram_auth'},
    'accounts.tasks.reclaim_account_task': {'queue': 'telegram_reclaim'},
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')