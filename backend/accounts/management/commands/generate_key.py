from django.core.management.base import BaseCommand
from accounts.services.encryption import EncryptionService


class Command(BaseCommand):
    help = 'Generate a new encryption master key'

    def handle(self, *args, **options):
        key = EncryptionService.generate_master_key()
        self.stdout.write(self.style.SUCCESS(f'Generated master key:'))
        self.stdout.write(f'ENCRYPTION_KEY={key}')
        self.stdout.write(self.style.WARNING('\nВАЖНО: Сохраните этот ключ в безопасном месте!'))
        self.stdout.write('Добавьте в переменные окружения как ENCRYPTION_KEY')