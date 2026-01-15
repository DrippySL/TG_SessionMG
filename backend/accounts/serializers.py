from rest_framework import serializers
from .models import TelegramAccount, AccountAuditLog, GlobalAppSettings


class GlobalAppSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalAppSettings
        fields = ['id', 'api_id', 'api_hash', 'app_name', 'app_version', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class TelegramAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramAccount
        fields = [
            'id', 'phone_number', 'employee_id', 'employee_fio', 'account_note',
            'session_updated_at', 'is_2fa_enabled', 'last_checked',
            'account_status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AccountAuditLogSerializer(serializers.ModelSerializer):
    account_phone = serializers.CharField(source='account.phone_number', read_only=True)

    class Meta:
        model = AccountAuditLog
        fields = [
            'id', 'account', 'account_phone', 'action_type',
            'action_details', 'performed_by', 'ip_address', 'created_at'
        ]
        read_only_fields = fields
