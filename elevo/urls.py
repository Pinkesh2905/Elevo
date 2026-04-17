# elevo/elevo/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')), 
    path('practice/', include('practice.urls')),
    path('aptitude/', include('aptitude.urls')),
    path('mock-interview/', include('mock_interview.urls')),
    path('tutor/', include('tutor.urls', namespace='tutor')),
    path('chat/', include('chat.urls', namespace='chat')),
    path('org/', include('organizations.urls', namespace='organizations')),
    path('assessments/', include('assessments.urls', namespace='assessments')),
    
    # Django's built-in authentication URLs (for login, logout, password reset)
    # These provide 'login', 'logout', 'password_reset', etc. view names globally.
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # The 'users' app handles custom signup and profile management
    path('users/', include('users.urls')), 
    
    
]

# Development-only media serving (or explicit insecure override).
# In production, media should be served by the platform/storage layer.
from django.urls import re_path
from django.views.static import serve

if settings.DEBUG or getattr(settings, 'SERVE_MEDIA_INSECURE', False):
    urlpatterns += [
        re_path(r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'), serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]
