# elevo/users/urls.py
from django.urls import path
from . import views

app_name = 'users'  # Namespace for this app's URLs

urlpatterns = [
    # Authentication URLs
    path('signup/', views.signup, name='signup'),
    path('login/', views.custom_login, name='login'),
    path('onboarding/', views.onboarding_wizard, name='onboarding_wizard'),
    
    # Email Verification URLs
    path('verify-email-sent/', views.verify_email_sent, name='verify_email_sent'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    
    # Password Reset URLs
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    
    # Profile URLs
    path('profile/', views.profile, name='profile'),
    path('profile/analyze-resume/', views.analyze_profile_resume, name='analyze_resume'),
    path('tutor-application/', views.tutor_application, name='tutor_application'),
    
    # Account Management URLs
    path('settings/', views.account_settings, name='account_settings'),
    path('change-email/', views.change_email, name='change_email'),
    path('verify-email-change/<str:token>/', views.verify_email_change, name='verify_email_change'),
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # Admin URLs
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/toggle-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('admin/approve-tutor/<int:user_id>/', views.admin_approve_tutor, name='approve_tutor'),
    path('admin/reject-tutor/<int:user_id>/', views.admin_reject_tutor, name='reject_tutor'),

    # Public profile URL (keep last so it does not swallow specific routes)
    path('<str:username>/', views.public_profile, name='public_profile'),
]
