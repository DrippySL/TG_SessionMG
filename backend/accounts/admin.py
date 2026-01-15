from django.contrib import admin
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import TelegramAccount, AccountAuditLog, GlobalAppSettings


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GlobalAppSettings)
class GlobalAppSettingsAdmin(admin.ModelAdmin):
    list_display = ('app_name', 'api_id', 'is_active', 'created_at')
    list_filter = ('is_active',)
    fieldsets = (
        (_('Информация о приложении'), {
            'fields': ('app_name', 'app_version', 'is_active')
        }),
        (_('Учетные данные Telegram API'), {
            'fields': ('api_id', 'api_hash'),
            'description': _('ВАЖНО: Эти учетные данные будут использоваться для ВСЕХ корпоративных аккаунтов')
        }),
        (_('Метаданные'), {
            'fields': ('created_at', 'updated_at')
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def has_add_permission(self, request):
        return GlobalAppSettings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return request.user.is_superuser


@admin.register(TelegramAccount)
class TelegramAccountAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'employee_fio', 'employee_id', 'account_status', 'session_updated_at', 'created_at', 'account_actions')
    list_filter = ('account_status', 'is_2fa_enabled')
    search_fields = ('phone_number', 'employee_id', 'employee_fio', 'account_note')
    readonly_fields = ('session_hash', 'encryption_version', 'created_at', 'updated_at', 'account_actions', 'session_updated_at', 'last_checked')
    
    # Exclude encrypted fields from the form
    exclude = ('encrypted_api_id', 'encrypted_api_hash', 'encrypted_session', 'encrypted_recovery_email')
    
    fieldsets = (
        (_('Информация об аккаунте'), {
            'fields': ('phone_number', 'employee_fio', 'employee_id', 'account_note', 'account_status')
        }),
        (_('Информация о безопасности'), {
            'fields': ('session_updated_at', 'session_hash', 'is_2fa_enabled', 'last_checked')
        }),
        (_('Действия'), {
            'fields': ('account_actions',),
            'description': _('Действия через React админ-панель')
        }),
        (_('Метаданные'), {
            'fields': ('encryption_version', 'created_at', 'updated_at')
        }),
    )
    
    # Fix: Explicitly define actions as a list to avoid the TypeError
    actions = []

    def account_actions(self, obj):
        if obj.account_status != 'active':
            return format_html('<span style="color: gray;">Доступно только для активных аккаунтов</span>')
        
        return format_html(
            '<a class="button" href="{}?account={}">Сменить пароль</a>&nbsp;'
            '<a class="button" href="{}?account={}">Удалить сессию</a>&nbsp;'
            '<a class="button" href="{}?account={}">Просмотр деталей</a>',
            reverse('admin:change_password'),
            obj.id,
            reverse('admin:delete_session'),
            obj.id,
            reverse('admin:view_details'),
            obj.id
        )
    account_actions.short_description = _('Действия')
    account_actions.allow_tags = True

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    # Disable add permission to prevent the FieldError
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('change-password/', self.admin_site.admin_view(self.change_password_view), name='change_password'),
            path('delete-session/', self.admin_site.admin_view(self.delete_session_view), name='delete_session'),
            path('view-details/', self.admin_site.admin_view(self.view_details_view), name='view_details'),
        ]
        return custom_urls + urls

    def change_password_view(self, request):
        if not request.user.is_superuser:
            return HttpResponseRedirect(reverse('admin:index'))
        
        account_id = request.GET.get('account')
        if account_id:
            from .services.telegram_actions import change_password
            result = change_password(account_id)
            self.message_user(request, result)
        return HttpResponseRedirect(reverse('admin:accounts_telegramaccount_changelist'))

    def delete_session_view(self, request):
        if not request.user.is_superuser:
            return HttpResponseRedirect(reverse('admin:index'))
        
        account_id = request.GET.get('account')
        if account_id:
            from .services.telegram_actions import delete_session
            result = delete_session(account_id)
            self.message_user(request, result)
        return HttpResponseRedirect(reverse('admin:accounts_telegramaccount_changelist'))

    def view_details_view(self, request):
        if not request.user.is_superuser:
            return HttpResponseRedirect(reverse('admin:index'))
        
        account_id = request.GET.get('account')
        if account_id:
            account = TelegramAccount.objects.get(id=account_id)
            from .services.encryption import EncryptionService
            encryptor = EncryptionService()
            
            details = f"Аккаунт {account.phone_number}: Сотрудник: {account.employee_fio}, Статус: {account.account_status}"
            self.message_user(request, details)
        return HttpResponseRedirect(reverse('admin:accounts_telegramaccount_changelist'))


@admin.register(AccountAuditLog)
class AccountAuditLogAdmin(ReadOnlyAdmin):
    list_display = ('account', 'action_type', 'performed_by', 'created_at')
    list_filter = ('action_type',)
    search_fields = ('account__phone_number', 'performed_by', 'action_type')
    readonly_fields = ('account', 'action_type', 'action_details', 'performed_by', 'ip_address', 'created_at')

    def has_module_permission(self, request):
        return request.user.is_superuser


admin.site.site_header = _("Система управления Telegram аккаунтами")
admin.site.site_title = _("Telegram Админ")
admin.site.index_title = _("Добро пожаловать в систему управления Telegram аккаунтами")

admin.site.unregister(Group)
