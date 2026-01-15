import asyncio
import sys
from django.core.management.base import BaseCommand
from accounts.services.session_manager import SessionManager
from accounts.models import GlobalAppSettings
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import PhoneCodeInvalidError, PhoneCodeExpiredError, SessionPasswordNeededError
from asgiref.sync import sync_to_async


class Command(BaseCommand):
    help = 'Setup a new corporate Telegram account via command line'

    def add_arguments(self, parser):
        parser.add_argument('phone_number', type=str, help='Phone number (e.g., +79991234567)')
        parser.add_argument('employee_id', type=str, help='Employee ID')
        parser.add_argument('employee_fio', type=str, help='Employee Full Name')
        parser.add_argument('account_note', type=str, help='Account description')
        parser.add_argument('--recovery-email', type=str, help='Recovery email')

    def handle(self, *args, **options):
        asyncio.run(self.setup_account_async(options))

    async def setup_account_async(self, options):
        phone = options['phone_number']
        employee_id = options['employee_id']
        employee_fio = options['employee_fio']
        note = options['account_note']
        recovery_email = options.get('recovery_email')

        self.stdout.write(f'Setting up account {phone}')
        self.stdout.write(f'Employee ID: {employee_id}')
        self.stdout.write(f'Employee FIO: {employee_fio}')
        self.stdout.write(f'Note: {note}')

        try:
            # Проверяем глобальные настройки
            settings = await sync_to_async(GlobalAppSettings.objects.filter(is_active=True).first)()
            if not settings:
                self.stdout.write(self.style.ERROR('ERROR: Global app settings not configured!'))
                return
                
            api_id, api_hash = settings.api_id, settings.api_hash
            
            if not recovery_email:
                recovery_email = input('Enter corporate recovery email: ').strip()

            # Проверяем email
            if not recovery_email.endswith('@ваша-компания.com'):
                self.stdout.write(self.style.WARNING('WARNING: Recovery email is not on corporate domain!'))
                confirm = input('Continue anyway? (yes/no): ').strip().lower()
                if confirm != 'yes':
                    return

            # Создаем сессию
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()

            # Запрашиваем код подтверждения
            try:
                await client.send_code_request(phone)
                code = input('Enter code from Telegram: ').strip()

                await client.sign_in(phone, code)
            except PhoneCodeInvalidError:
                self.stdout.write(self.style.ERROR('Invalid code. Please try again.'))
                return
            except PhoneCodeExpiredError:
                self.stdout.write(self.style.ERROR('Code expired. Please try again.'))
                return
            except SessionPasswordNeededError:
                self.stdout.write(self.style.ERROR('2FA password required. This is not supported in CLI mode.'))
                return

            # Получаем данные сессии
            session_string = client.session.save()
            session_data = session_string.encode('utf-8')

            # Сохраняем в БД
            manager = SessionManager()
            success = await sync_to_async(manager.save_account_session)(
                phone_number=phone,
                session_data=session_data,
                recovery_email=recovery_email,
                employee_id=employee_id,
                employee_fio=employee_fio,
                account_note=note,
                account_status='active'
            )

            if success:
                self.stdout.write(self.style.SUCCESS(f'✓ Account {phone} successfully configured'))
                self.stdout.write(f'Recovery email: {recovery_email}')
                self.stdout.write(f'Using global API ID: {api_id}')
            else:
                self.stdout.write(self.style.ERROR(f'✗ Error saving account {phone}'))

            await client.disconnect()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))