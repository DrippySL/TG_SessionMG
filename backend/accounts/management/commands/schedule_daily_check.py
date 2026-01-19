from django.core.management.base import BaseCommand
from django.utils.timezone import now
from accounts.models import TelegramAccount
from accounts.tasks import bulk_check_accounts_task
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Schedule daily check for all active accounts'

    def handle(self, *args, **options):
        # Получаем все активные аккаунты
        active_accounts = TelegramAccount.objects.filter(
            account_status='active'
        ).values_list('id', flat=True)
        
        account_ids = list(active_accounts)
        
        if not account_ids:
            self.stdout.write(self.style.WARNING('No active accounts found'))
            return
        
        self.stdout.write(f'Scheduling check for {len(account_ids)} active accounts')
        
        # Создаем задачу в очереди
        from accounts.models import TaskQueue
        task = TaskQueue.objects.create(
            task_type='bulk_check',
            account_ids=account_ids,
            parameters={'scheduled': True},
            created_by='Система'
        )
        
        # Запускаем задачу Celery
        bulk_check_accounts_task.delay(account_ids, task.id)
        
        self.stdout.write(self.style.SUCCESS(f'Scheduled task {task.id} for {len(account_ids)} accounts'))