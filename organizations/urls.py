from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('', views.my_organization, name='my_org'),
    path('create/', views.create_org, name='create_org'),
    path('dashboard/', views.org_dashboard, name='dashboard'),
    path('members/', views.manage_members, name='members'),
    path('invite/', views.invite_student, name='invite_student'),
    path('invite/bulk/', views.bulk_invite_students, name='bulk_invite_students'),
    path('verify-domain/', views.verify_domain, name='verify_domain'),
    path('join/<str:token>/', views.join_org, name='join_org'),
    path('remove/<int:membership_id>/', views.remove_member, name='remove_member'),
    path('leave/', views.leave_org, name='leave_org'),
    path('subscription/', views.subscription_detail, name='subscription'),
    path('upgrade-required/', views.upgrade_required, name='upgrade_required'),
    path('request-sponsorship/', views.request_sponsorship, name='request_sponsorship'),
    path('cancel-invite/<int:invite_id>/', views.cancel_invitation, name='cancel_invite'),
    path('pricing/', views.pricing, name='pricing'),
    # Legacy self-serve payment flows removed for B2B transition.
    # --- Multi-Tenant Hardening ---
    path('change-role/<int:membership_id>/', views.change_member_role, name='change_member_role'),
    path('transfer-ownership/<int:membership_id>/', views.transfer_ownership, name='transfer_ownership'),
    path('bulk-action/', views.bulk_member_action, name='bulk_member_action'),
    path('csv-template/', views.csv_template_download, name='csv_template_download'),
    # --- Analytics ---
    path('analytics/', views.org_analytics, name='org_analytics'),
    path('analytics/export/csv/', views.export_analytics_csv, name='export_analytics_csv'),
    path('analytics/export/pdf/', views.export_analytics_pdf, name='export_analytics_pdf'),
    # --- AI Cost Dashboard ---
    path('ai-dashboard/', views.ai_cost_dashboard, name='ai_dashboard'),
]
