from django.db import models


class GlobalAppSettings(models.Model):
    """Глобальные настройки приложения Telegram (один api_id/api_hash на все аккаунты)"""
    api_id = models.IntegerField(unique=True)
    api_hash = models.CharField(max_length=200)
    app_name = models.CharField(max_length=100, default='Corporate Telegram Manager')
    app_version = models.CharField(max_length=20, default='1.0')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'global_app_settings'
        verbose_name = 'Global App Settings'
        verbose_name_plural = 'Global App Settings'

    def __str__(self):
        return f"{self.app_name} (ID: {self.api_id})"


class ProxyServer(models.Model):
    """Прокси-серверы для подключения аккаунтов"""
    name = models.CharField(max_length=100)
    host = models.CharField(max_length=200)
    port = models.IntegerField()
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    proxy_type = models.CharField(max_length=20, default='socks5', choices=[
        ('socks5', 'SOCKS5'),
        ('http', 'HTTP'),
        ('mtproto', 'MTProto')
    ])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'proxy_servers'
        verbose_name = 'Proxy Server'
        verbose_name_plural = 'Proxy Servers'

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"


class TelegramAccount(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_2fa', 'Pending 2FA'),
        ('pending_reauthorization', 'Pending Reauthorization'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('reclaimed', 'Reclaimed'),
        ('dead', 'Dead'),
        ('flood', 'Flood Wait'),
    ]
    
    ACTIVITY_STATUS_CHOICES = [
        ('active', 'Active'),
        ('dead', 'Dead'),
        ('flood', 'Flood'),
    ]

    phone_number = models.CharField(max_length=20, unique=True)
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    employee_fio = models.CharField(max_length=200, blank=True, null=True)
    account_note = models.TextField(blank=True, null=True)
    
    # КРИТИЧЕСКИ ВАЖНЫЕ ДАННЫЕ (зашифрованы)
    encrypted_api_id = models.BinaryField(blank=True, null=True)
    encrypted_api_hash = models.BinaryField(blank=True, null=True)
    encrypted_session = models.BinaryField(blank=True, null=True)
    encrypted_recovery_email = models.BinaryField(blank=True, null=True)
    encrypted_phone_code_hash = models.BinaryField(blank=True, null=True)  # Добавлено для хранения временного кода подтверждения
    
    # Метаданные сессии
    session_updated_at = models.DateTimeField(blank=True, null=True)
    session_hash = models.CharField(max_length=64, blank=True, null=True)
    
    # Состояние аккаунта
    is_2fa_enabled = models.BooleanField(default=False)
    last_checked = models.DateTimeField(blank=True, null=True)
    account_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    
    # Новые поля по ТЗ
    last_ping = models.DateTimeField(blank=True, null=True, verbose_name='Последняя активность')
    activity_status = models.CharField(max_length=20, choices=ACTIVITY_STATUS_CHOICES, default='active', verbose_name='Статус активности')
    device_params = models.JSONField(default=dict, blank=True, null=True, verbose_name='Параметры устройства')
    proxy = models.ForeignKey(ProxyServer, on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Прокси-сервер', related_name='accounts')
    
    # Безопасность
    encryption_version = models.IntegerField(default=1)
    
    # Аудит
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'telegram_accounts'
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['account_status']),
            models.Index(fields=['employee_id']),
            models.Index(fields=['employee_fio']),
            models.Index(fields=['last_ping']),
            models.Index(fields=['activity_status']),
        ]

    def __str__(self):
        return f"{self.phone_number} ({self.account_status})"

    @property
    def health_indicator(self):
        """Индикатор здоровья аккаунта на основе last_ping"""
        if not self.last_ping:
            return 'gray'

        from django.utils.timezone import now
        current_time = now()
        lp_time = self.last_ping

        # Если last_ping наивный (без часового пояса), преобразуем в aware
        if not lp_time.tzinfo:
            from django.utils.timezone import make_aware
            lp_time = make_aware(lp_time)

        time_diff = (current_time - lp_time).total_seconds()

        if time_diff < 86400:
            return 'green'
        elif time_diff < 604800:
            return 'yellow'
        else:
            return 'red'


class AccountAuditLog(models.Model):
    account = models.ForeignKey(TelegramAccount, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=50)
    action_details = models.JSONField(blank=True, null=True)
    performed_by = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'account_audit_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} for {self.account.phone_number}"


class TaskQueue(models.Model):
    """Очередь задач для проверки аккаунтов"""
    TASK_TYPE_CHOICES = [
        ('check_account', 'Проверка аккаунта'),
        ('bulk_check', 'Групповая проверка'),
        ('reauthorize', 'Повторная авторизация'),
        ('reclaim', 'Возврат аккаунта'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('processing', 'В процессе'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
        ('cancelled', 'Отменено'),
    ]
    
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
    account = models.ForeignKey(TelegramAccount, on_delete=models.CASCADE, blank=True, null=True)
    account_ids = models.JSONField(blank=True, null=True, help_text='ID аккаунтов для групповой операции')
    parameters = models.JSONField(default=dict, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0, help_text='Прогресс в процентах')
    result = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_by = models.CharField(max_length=100, blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'task_queue'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['task_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.status}"