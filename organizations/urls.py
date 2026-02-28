from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('', views.my_organization, name='my_org'),
    path('create/', views.create_org, name='create_org'),
    path('dashboard/', views.org_dashboard, name='dashboard'),
    path('members/', views.manage_members, name='members'),
    path('invite/', views.invite_student, name='invite_student'),
    path('join/<str:token>/', views.join_org, name='join_org'),
    path('remove/<int:membership_id>/', views.remove_member, name='remove_member'),
    path('leave/', views.leave_org, name='leave_org'),
    path('subscription/', views.subscription_detail, name='subscription'),
    path('upgrade-required/', views.upgrade_required, name='upgrade_required'),
    path('request-sponsorship/', views.request_sponsorship, name='request_sponsorship'),
    path('cancel-invite/<int:invite_id>/', views.cancel_invitation, name='cancel_invite'),
    path('pricing/', views.pricing, name='pricing'),
    path('checkout-individual/', views.checkout_individual, name='checkout_individual'),
]
