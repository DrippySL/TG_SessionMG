from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.db import transaction
from django.utils.timezone import now
from django.db.models import Q

from .models import TelegramAccount, AccountAuditLog, GlobalAppSettings, TaskQueue, ProxyServer
from .serializers import (
    TelegramAccountSerializer, AccountAuditLogSerializer,
    GlobalAppSettingsSerializer, TaskQueueSerializer,
    ProxyServerSerializer, BulkActionSerializer, DeviceParamsSerializer
)
from .services import change_password, send_code, verify_code, delete_session, get_account_details, reclaim_account, check_api_credentials, reauthorize_account, verify_reauthorization
from .tasks import check_account_task, bulk_check_accounts_task, reauthorize_account_task, reclaim_account_task


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class TelegramAccountList(generics.ListAPIView):
    serializer_class = TelegramAccountSerializer
    permission_classes = [IsSuperUser]

    def get_queryset(self):
        queryset = TelegramAccount.objects.using('telegram_db').all()
        
        # Поиск
        search_term = self.request.query_params.get('search')
        if search_term:
            queryset = queryset.filter(
                Q(phone_number__icontains=search_term) |
                Q(employee_id__icontains=search_term) |
                Q(employee_fio__icontains=search_term)
            )
        
        # Фильтрация по статусу
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(account_status=status_filter)
        
        # Фильтрация по активности
        activity_filter = self.request.query_params.get('activity_status')
        if activity_filter:
            queryset = queryset.filter(activity_status=activity_filter)
        
        # Фильтрация по дате последней активности
        last_ping_from = self.request.query_params.get('last_ping_from')
        if last_ping_from:
            queryset = queryset.filter(last_ping__gte=last_ping_from)
        
        last_ping_to = self.request.query_params.get('last_ping_to')
        if last_ping_to:
            queryset = queryset.filter(last_ping__lte=last_ping_to)
        
        # Сортировка по последней активности
        sort_by = self.request.query_params.get('sort_by', '-last_ping')
        queryset = queryset.order_by(sort_by)
        
        return queryset


class TelegramAccountDetail(generics.RetrieveUpdateAPIView):
    serializer_class = TelegramAccountSerializer
    permission_classes = [IsSuperUser]

    def get_queryset(self):
        return TelegramAccount.objects.using('telegram_db').all()
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Обновление employee_fio и employee_id
        if 'employee_fio' in request.data:
            instance.employee_fio = request.data.get('employee_fio', instance.employee_fio)
        if 'employee_id' in request.data:
            instance.employee_id = request.data.get('employee_id', instance.employee_id)
        if 'account_note' in request.data:
            instance.account_note = request.data.get('account_note', instance.account_note)
        
        # Обновление device_params
        if 'device_params' in request.data:
            device_params_serializer = DeviceParamsSerializer(data=request.data.get('device_params', {}))
            if device_params_serializer.is_valid():
                instance.device_params = device_params_serializer.validated_data
            else:
                return Response(device_params_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Обновление proxy
        if 'proxy' in request.data:
            proxy_id = request.data.get('proxy')
            if proxy_id:
                try:
                    proxy = ProxyServer.objects.get(id=proxy_id)
                    instance.proxy = proxy
                except ProxyServer.DoesNotExist:
                    return Response({'error': 'Proxy server not found'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                instance.proxy = None
        
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class AuditLogList(generics.ListAPIView):
    serializer_class = AccountAuditLogSerializer
    permission_classes = [IsSuperUser]

    def get_queryset(self):
        queryset = AccountAuditLog.objects.using('telegram_db').all()
        
        # Фильтрация по аккаунту
        account_id = self.request.query_params.get('account_id')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
        
        return queryset.order_by('-created_at')[:100]


class ChangePasswordView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request, pk):
        try:
            old_password = request.data.get('old_password', '')
            new_password = request.data.get('new_password', '')
            
            if not new_password:
                new_password = None
                
            result = change_password(pk, old_password if old_password else None, new_password)
            if isinstance(result, dict) and 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response({'message': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeleteSessionView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request, pk):
        try:
            result = delete_session(pk)
            if isinstance(result, dict) and 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response({'message': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetAccountDetailsView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request, pk):
        try:
            result = get_account_details(pk)
            if isinstance(result, dict) and 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response({'details': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendCodeView(APIView):
    permission_classes = []

    @method_decorator(ensure_csrf_cookie)
    def post(self, request):
        try:
            phone = request.data.get('phone_number')
            employee_id = request.data.get('employee_id')
            employee_fio = request.data.get('employee_fio')
            account_note = request.data.get('account_note')
            recovery_email = request.data.get('recovery_email')

            result = send_code(phone, employee_id, employee_fio, account_note, recovery_email)
            
            if isinstance(result, dict):
                if 'error' in result:
                    return Response(result, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response(result)
            else:
                return Response({'message': result})
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyCodeView(APIView):
    permission_classes = []

    @method_decorator(ensure_csrf_cookie)
    def post(self, request):
        try:
            phone = request.data.get('phone_number')
            code = request.data.get('verification_code')
            employee_id = request.data.get('employee_id')
            employee_fio = request.data.get('employee_fio')
            account_note = request.data.get('account_note')
            recovery_email = request.data.get('recovery_email')
            two_factor_password = request.data.get('two_factor_password')

            result = verify_code(phone, code, employee_id, employee_fio, account_note, recovery_email, two_factor_password)
            
            if isinstance(result, dict):
                if 'error' in result:
                    if 'requires_2fa' in result and result['requires_2fa']:
                        return Response(result, status=status.HTTP_200_OK)
                    else:
                        return Response(result, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response(result)
            else:
                return Response({'message': result})
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GlobalAppSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = GlobalAppSettingsSerializer
    permission_classes = [IsSuperUser]
    
    def get_object(self):
        obj, created = GlobalAppSettings.objects.using('telegram_db').get_or_create(
            is_active=True,
            defaults={
                'api_id': 0,
                'api_hash': '',
                'app_name': 'Corporate Telegram Manager',
                'app_version': '1.0'
            }
        )
        return obj
    
    def put(self, request, *args, **kwargs):
        api_id = request.data.get('api_id')
        api_hash = request.data.get('api_hash')
        
        if api_id and api_hash:
            try:
                is_valid, message = check_api_credentials(int(api_id), api_hash)
                if not is_valid:
                    return Response(
                        {'error': f'Invalid API credentials: {message}'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                return Response(
                    {'error': f'Error checking API credentials: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return super().put(request, *args, **kwargs)


class ReclaimAccountView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request, pk):
        try:
            two_factor_password = request.data.get('two_factor_password', None)
            
            # Выполняем немедленно без очереди задач
            result = reclaim_account(pk, two_factor_password)
            
            return Response(result)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReauthorizeAccountView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request, pk):
        try:
            two_factor_password = request.data.get('two_factor_password', None)

            result = reauthorize_account(pk, two_factor_password)

            return Response(result)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyReauthorizationView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request, pk):
        try:
            code = request.data.get('verification_code')
            two_factor_password = request.data.get('two_factor_password', None)
            
            if not code:
                return Response({'error': 'Код подтверждения обязателен'}, status=status.HTTP_400_BAD_REQUEST)

            result = verify_reauthorization(pk, code, two_factor_password)

            # Если успешно завершена повторная авторизация, обновляем связанную задачу
            if isinstance(result, dict) and 'message' in result:
                try:
                    # Ищем задачу в статусе processing для этого аккаунта
                    task = TaskQueue.objects.filter(
                        account_id=pk,
                        task_type='reauthorize',
                        status='processing'
                    ).first()

                    if task:
                        task.status = 'completed'
                        task.result = result
                        task.completed_at = now()
                        task.save()
                except Exception as task_error:
                    logger.warning(f"Не удалось обновить задачу: {task_error}")

            if isinstance(result, dict):
                if 'error' in result:
                    if 'requires_2fa' in result and result['requires_2fa']:
                        return Response(result, status=status.HTTP_200_OK)
                    else:
                        return Response(result, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response(result)
            else:
                return Response({'message': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthCheckView(APIView):
    """
    Authentication check endpoint that works without requiring login
    Used by frontend to check auth status
    """
    
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return JsonResponse({
            'is_authenticated': request.user.is_authenticated,
            'is_superuser': request.user.is_superuser,
            'username': request.user.username if request.user.is_authenticated else '',
            'email': request.user.email if request.user.is_authenticated else '',
            'csrf_token': get_token(request)
        })


class GetCSRFToken(APIView):
    """API endpoint to get CSRF token"""
    authentication_classes = []
    permission_classes = []
    
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return JsonResponse({
            'csrf_token': get_token(request),
            'detail': 'CSRF token set in cookie'
        })


class CheckAPICredentialsView(APIView):
    """Check Telegram API credentials"""
    permission_classes = [IsSuperUser]
    
    def post(self, request):
        try:
            api_id = request.data.get('api_id')
            api_hash = request.data.get('api_hash')
            
            if not api_id or not api_hash:
                return Response(
                    {'error': 'API ID and API Hash are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            is_valid, message = check_api_credentials(int(api_id), api_hash)
            
            return Response({
                'is_valid': is_valid,
                'message': message
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TaskQueueList(generics.ListAPIView):
    serializer_class = TaskQueueSerializer
    permission_classes = [IsSuperUser]
    
    def get_queryset(self):
        queryset = TaskQueue.objects.all().order_by('-created_at')
        
        # Фильтрация по статусу
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Фильтрация по типу задачи
        task_type = self.request.query_params.get('task_type')
        if task_type:
            queryset = queryset.filter(task_type=task_type)
        
        return queryset[:50]


class TaskQueueDetail(generics.RetrieveAPIView):
    serializer_class = TaskQueueSerializer
    permission_classes = [IsSuperUser]
    queryset = TaskQueue.objects.all()


class CancelTaskView(APIView):
    permission_classes = [IsSuperUser]
    
    def post(self, request, pk):
        try:
            task = TaskQueue.objects.get(id=pk)
            
            if task.status not in ['pending', 'processing']:
                return Response(
                    {'error': 'Задачу можно отменить только в статусе "Ожидает" или "В процессе"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            task.status = 'cancelled'
            task.completed_at = now()
            task.save()
            
            return Response({'message': 'Задача отменена'})
            
        except TaskQueue.DoesNotExist:
            return Response(
                {'error': 'Задача не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BulkActionView(APIView):
    permission_classes = [IsSuperUser]
    
    def post(self, request):
        serializer = BulkActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        account_ids = serializer.validated_data['account_ids']
        action = serializer.validated_data['action']
        
        try:
            # Проверяем существование аккаунтов (используем ту же базу данных, что и для аккаунтов)
            accounts_count = TelegramAccount.objects.using('telegram_db').filter(id__in=account_ids).count()
            if accounts_count != len(account_ids):
                return Response(
                    {'error': f'Найдено только {accounts_count} из {len(account_ids)} аккаунтов'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Создаем задачу в очереди
            task = TaskQueue.objects.create(
                task_type='bulk_check' if action == 'check' else action,
                account_ids=account_ids,
                parameters={'action': action},
                created_by=request.user.username
            )
            
            # Запускаем соответствующую задачу Celery
            if action == 'check':
                bulk_check_accounts_task.delay(account_ids, task.id)
                message = f'Проверка {len(account_ids)} аккаунтов поставлена в очередь'
            else:
                # Для других действий нужно реализовать отдельные задачи
                return Response(
                    {'error': f'Действие {action} еще не реализовано для групповых операций'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'message': message,
                'task_id': task.id,
                'account_count': len(account_ids)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProxyServerList(generics.ListCreateAPIView):
    serializer_class = ProxyServerSerializer
    permission_classes = [IsSuperUser]
    queryset = ProxyServer.objects.all()


class ProxyServerDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProxyServerSerializer
    permission_classes = [IsSuperUser]
    queryset = ProxyServer.objects.all()


class DeviceParamsUpdateView(APIView):
    permission_classes = [IsSuperUser]
    
    def post(self, request, pk):
        try:
            account = TelegramAccount.objects.using('telegram_db').get(id=pk)
            serializer = DeviceParamsSerializer(data=request.data)
            
            if serializer.is_valid():
                account.device_params = serializer.validated_data
                account.save()
                return Response({'message': 'Параметры устройства обновлены'})
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TelegramAccount.DoesNotExist:
            return Response({'error': 'Аккаунт не найден'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SecurityAlertsView(APIView):
    """API для получения результатов проверки безопасности"""
    permission_classes = [IsSuperUser]
    
    def get(self, request):
        try:
            # Получаем аккаунты с информацией о безопасности
            accounts = TelegramAccount.objects.using('telegram_db').all()
            
            security_results = []
            for account in accounts:
                security_info = account.device_params.get('security_info', {}) if account.device_params else {}
                
                security_results.append({
                    'id': account.id,
                    'phone_number': account.phone_number,
                    'employee_fio': account.employee_fio,
                    'employee_id': account.employee_id,
                    'has_security_alert': security_info.get('has_security_alert', False),
                    'alert_message': security_info.get('alert_message', ''),
                    'last_security_check': security_info.get('last_security_check', ''),
                    'account_status': account.account_status,
                    'activity_status': account.activity_status,
                    'last_ping': account.last_ping
                })
            
            return Response(security_results)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EditAccountView(APIView):
    """API для редактирования employee_fio и employee_id"""
    permission_classes = [IsSuperUser]
    
    def post(self, request, pk):
        try:
            account = TelegramAccount.objects.using('telegram_db').get(id=pk)
            
            if 'employee_fio' in request.data:
                account.employee_fio = request.data['employee_fio']
            if 'employee_id' in request.data:
                account.employee_id = request.data['employee_id']
            if 'account_note' in request.data:
                account.account_note = request.data['account_note']
            
            account.save()
            
            # Логируем действие
            AccountAuditLog.objects.using('telegram_db').create(
                account=account,
                action_type='account_updated',
                action_details={
                    'employee_fio': account.employee_fio,
                    'employee_id': account.employee_id,
                    'account_note': account.account_note
                },
                performed_by=request.user.username
            )
            
            return Response({'message': 'Данные аккаунта успешно обновлены'})
            
        except TelegramAccount.DoesNotExist:
            return Response({'error': 'Аккаунт не найден'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)