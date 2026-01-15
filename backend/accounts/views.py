from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.http import JsonResponse
from django.middleware.csrf import get_token
from .models import TelegramAccount, AccountAuditLog, GlobalAppSettings
from .serializers import (
    TelegramAccountSerializer, AccountAuditLogSerializer,
    GlobalAppSettingsSerializer
)
from .services import change_password, send_code, verify_code, delete_session, get_account_details, reclaim_account, check_api_credentials, reauthorize_account, verify_reauthorization


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class TelegramAccountList(generics.ListAPIView):
    serializer_class = TelegramAccountSerializer
    permission_classes = [IsSuperUser]

    def get_queryset(self):
        return TelegramAccount.objects.using('telegram_db').all()


class TelegramAccountDetail(generics.RetrieveAPIView):
    serializer_class = TelegramAccountSerializer
    permission_classes = [IsSuperUser]

    def get_queryset(self):
        return TelegramAccount.objects.using('telegram_db').all()


class AuditLogList(generics.ListAPIView):
    serializer_class = AccountAuditLogSerializer
    permission_classes = [IsSuperUser]

    def get_queryset(self):
        return AccountAuditLog.objects.using('telegram_db').all()[:100]


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
            result = reclaim_account(pk, two_factor_password)
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


class ReauthorizeAccountView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request, pk):
        try:
            two_factor_password = request.data.get('two_factor_password', None)
            result = reauthorize_account(pk, two_factor_password)
            if isinstance(result, dict):
                if 'error' in result:
                    return Response(result, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response(result)
            else:
                return Response({'message': result})
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
