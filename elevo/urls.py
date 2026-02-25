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
    path('posts/', include('posts.urls', namespace='posts')),
    path('chat/', include('chat.urls', namespace='chat')),
    path('org/', include('organizations.urls', namespace='organizations')),
    
    # Django's built-in authentication URLs (for login, logout, password reset)
    # These provide 'login', 'logout', 'password_reset', etc. view names globally.
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # The 'users' app handles custom signup and profile management
    path('users/', include('users.urls')), 
    
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
]

# Only for development: serve media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
