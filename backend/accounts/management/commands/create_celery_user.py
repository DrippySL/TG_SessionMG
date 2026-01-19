from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Create a Celery user for task management'

    def handle(self, *args, **options):
        username = 'celery_worker'
        email = 'celery@localhost'
        password = 'celery_password_123'

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User {username} already exists'))
            return

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=False
        )
        self.stdout.write(self.style.SUCCESS(f'Celery user {username} created successfully'))
        self.stdout.write(self.style.WARNING(f'Password: {password}'))