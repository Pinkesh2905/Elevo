from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('search-users/', views.search_users, name='search_users'),
    path('new/<str:username>/', views.start_chat, name='start_chat'),
    path('unread-count/', views.unread_count, name='unread_count'),
    path('<int:thread_id>/', views.chat_thread, name='thread'),
    path('<int:thread_id>/send/', views.send_message, name='send_message'),
    path('<int:thread_id>/stream/', views.thread_stream, name='thread_stream'),
    path('<int:thread_id>/fetch/', views.fetch_messages, name='fetch_messages'),
    path('<int:thread_id>/fetch-older/', views.fetch_older_messages, name='fetch_older_messages'),
    path('<int:thread_id>/presence/', views.update_presence, name='update_presence'),
    path('<int:thread_id>/typing/', views.update_typing_status, name='update_typing_status'),
    path('<int:thread_id>/status/', views.get_thread_status, name='thread_status'),
    path('message/<int:message_id>/react/', views.toggle_reaction, name='toggle_reaction'),
    path('message/<int:message_id>/edit/', views.edit_message, name='edit_message'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('<int:thread_id>/theme/', views.update_theme, name='update_theme'),
    path('message/<int:message_id>/edit/', views.edit_message, name='edit_message'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('<int:thread_id>/theme/', views.update_theme, name='update_theme'),
]
