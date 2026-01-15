from django.urls import path
from . import views

urlpatterns = [
    # Account management
    path('accounts/', views.TelegramAccountList.as_view(), name='account-list'),
    path('accounts/<int:pk>/', views.TelegramAccountDetail.as_view(), name='account-detail'),
    path('accounts/<int:pk>/reclaim/', views.ReclaimAccountView.as_view(), name='account-reclaim'),
    path('accounts/<int:pk>/change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('accounts/<int:pk>/delete-session/', views.DeleteSessionView.as_view(), name='delete-session'),
    path('accounts/<int:pk>/details/', views.GetAccountDetailsView.as_view(), name='account-details'),
    path('accounts/send-code/', views.SendCodeView.as_view(), name='send-code'),
    path('accounts/verify-code/', views.VerifyCodeView.as_view(), name='verify-code'),
    
    # Reauthorization
    path('accounts/<int:pk>/reauthorize/', views.ReauthorizeAccountView.as_view(), name='reauthorize-account'),
    path('accounts/<int:pk>/verify-reauthorization/', views.VerifyReauthorizationView.as_view(), name='verify-reauthorization'),
    
    # Global app settings
    path('settings/', views.GlobalAppSettingsView.as_view(), name='global-settings'),
    
    # Check API credentials
    path('check-api-credentials/', views.CheckAPICredentialsView.as_view(), name='check-api-credentials'),
    
    # Audit logs
    path('audit-logs/', views.AuditLogList.as_view(), name='audit-log-list'),
    
    # Auth check
    path('auth/check/', views.AuthCheckView.as_view(), name='auth-check'),
    
    # CSRF token
    path('auth/csrf/', views.GetCSRFToken.as_view(), name='get-csrf-token'),
]