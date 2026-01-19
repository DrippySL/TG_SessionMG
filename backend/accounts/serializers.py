from rest_framework import serializers
from .models import TelegramAccount, AccountAuditLog, GlobalAppSettings, TaskQueue, ProxyServer


class GlobalAppSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalAppSettings
        fields = ['id', 'api_id', 'api_hash', 'app_name', 'app_version', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ProxyServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProxyServer
        fields = ['id', 'name', 'host', 'port', 'username', 'password', 'proxy_type', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class TelegramAccountSerializer(serializers.ModelSerializer):
    health_indicator = serializers.CharField(read_only=True)
    proxy_details = ProxyServerSerializer(source='proxy', read_only=True)
    
    class Meta:
        model = TelegramAccount
        fields = [
            'id', 'phone_number', 'employee_id', 'employee_fio', 'account_note',
            'session_updated_at', 'is_2fa_enabled', 'last_checked',
            'account_status', 'last_ping', 'activity_status', 'device_params',
            'proxy', 'proxy_details', 'health_indicator',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'health_indicator']


class AccountAuditLogSerializer(serializers.ModelSerializer):
    account_phone = serializers.CharField(source='account.phone_number', read_only=True)

    class Meta:
        model = AccountAuditLog
        fields = [
            'id', 'account', 'account_phone', 'action_type',
            'action_details', 'performed_by', 'ip_address', 'created_at'
        ]
        read_only_fields = fields


class TaskQueueSerializer(serializers.ModelSerializer):
    account_phone = serializers.CharField(source='account.phone_number', read_only=True, allow_null=True)
    
    class Meta:
        model = TaskQueue
        fields = [
            'id', 'task_type', 'account', 'account_phone', 'account_ids',
            'parameters', 'status', 'progress', 'result', 'error_message',
            'created_by', 'started_at', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class BulkActionSerializer(serializers.Serializer):
    account_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text='Список ID аккаунтов для групповой операции'
    )
    action = serializers.CharField(
        required=True,
        help_text='Тип действия: check, reauthorize, reclaim'
    )


class DeviceParamsSerializer(serializers.Serializer):
    device_model = serializers.CharField(required=False, default='')
    system_version = serializers.CharField(required=False, default='')
    app_version = serializers.CharField(required=False, default='1.0')
    lang_code = serializers.CharField(required=False, default='ru')
    system_lang_code = serializers.CharField(required=False, default='ru')