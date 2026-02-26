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
    path('<int:thread_id>/typing/', views.update_typing_status, name='update_typing_status'),
    path('<int:thread_id>/status/', views.get_thread_status, name='thread_status'),
    path('message/<int:message_id>/react/', views.toggle_reaction, name='toggle_reaction'),
]
