from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('new/<str:username>/', views.start_chat, name='start_chat'),
    path('unread-count/', views.unread_count, name='unread_count'),
    path('<int:thread_id>/', views.chat_thread, name='thread'),
    path('<int:thread_id>/send/', views.send_message, name='send_message'),
    path('<int:thread_id>/fetch/', views.fetch_messages, name='fetch_messages'),
]
