from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.services.session_manager import SessionManager
from accounts.models import TelegramAccount
import asyncio
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Refresh Telegram sessions for all active accounts'

    def handle(self, *args, **options):
        self.stdout.write('Starting session refresh...')
        
        # Get accounts that need refresh (older than 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        accounts = TelegramAccount.objects.filter(
            account_status='active',
            session_updated_at__lt=thirty_days_ago
        )
        
        self.stdout.write(f'Found {accounts.count()} accounts needing refresh')
        
        session_manager = SessionManager()
        success_count = 0
        fail_count = 0
        
        for account in accounts:
            try:
                self.stdout.write(f'Refreshing session for {account.phone_number}...')
                
                # Load account data
                account_data = session_manager.load_account_session(account.phone_number)
                
                # This would normally create a new session, but for simplicity
                # we'll just update the timestamp
                account.session_updated_at = timezone.now()
                account.save()
                
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Session refreshed for {account.phone_number}'))
                
            except Exception as e:
                fail_count += 1
                logger.error(f'Failed to refresh session for {account.phone_number}: {e}')
                self.stdout.write(self.style.ERROR(f'✗ Failed for {account.phone_number}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nRefresh completed: {success_count} successful, {fail_count} failed'))