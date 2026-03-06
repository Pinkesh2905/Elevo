from django.urls import path
from django.contrib.auth import views as auth_views # Import Django's built-in auth views
from . import views

urlpatterns = [
    path('', views.home, name='home'), # Your main homepage, also acts as dashboard dispatcher
    path('dashboard-redirect/', views.dashboard_redirect, name='dashboard_redirect'), # Explicit redirect URL

    # Custom login view using Django's built-in LoginView, pointing to our template
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'), # CHANGED: 'core/login.html' to 'login.html'
    # Custom logout view
    # path('logout/', auth_views.LogoutView.as_view(next_page='landing'), name='logout'),
    path('logout/', views.custom_logout, name='logout'),
    path('landing/', views.landing, name='landing'),  # new route
    path('search/', views.search, name='search'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('data-processing-addendum/', views.data_processing_addendum, name='data_processing_addendum'),
]
