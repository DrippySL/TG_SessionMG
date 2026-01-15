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


class TelegramAccount(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_2fa', 'Pending 2FA'),
        ('pending_reauthorization', 'Pending Reauthorization'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('reclaimed', 'Reclaimed'),
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
        ]

    def __str__(self):
        return f"{self.phone_number} ({self.account_status})"


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