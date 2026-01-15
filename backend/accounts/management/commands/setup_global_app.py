from django.core.management.base import BaseCommand
from accounts.models import GlobalAppSettings

class Command(BaseCommand):
    help = 'Setup global Telegram application credentials'

    def add_arguments(self, parser):
        parser.add_argument('--api-id', type=int, required=True, help='Telegram API ID')
        parser.add_argument('--api-hash', type=str, required=True, help='Telegram API Hash')
        parser.add_argument('--app-name', type=str, default='Corporate Telegram Manager', help='Application name')
        parser.add_argument('--app-version', type=str, default='1.0', help='Application version')

    def handle(self, *args, **options):
        api_id = options['api_id']
        api_hash = options['api_hash']
        app_name = options['app_name']
        app_version = options['app_version']

        # Deactivate any existing settings
        GlobalAppSettings.objects.filter(is_active=True).update(is_active=False)

        # Create new active settings
        settings, created = GlobalAppSettings.objects.update_or_create(
            api_id=api_id,
            defaults={
                'api_hash': api_hash,
                'app_name': app_name,
                'app_version': app_version,
                'is_active': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created new global app settings: {app_name} (API ID: {api_id})'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated global app settings: {app_name} (API ID: {api_id})'))

        self.stdout.write(self.style.WARNING('\nВАЖНО: Эти credentials будут использоваться для ВСЕХ корпоративных аккаунтов'))