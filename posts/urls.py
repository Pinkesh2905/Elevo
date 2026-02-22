from django.urls import path
from . import views

app_name = 'posts'

urlpatterns = [
    # Feed
    path('', views.feed_view, name='feed'),
    
    # Post actions (specific patterns with prefixes)
    path('like/<uuid:post_id>/', views.toggle_like, name='toggle_like'),
    path('comment/<uuid:post_id>/', views.add_comment, name='add_comment'),
    path('repost/<uuid:post_id>/', views.repost, name='repost'),
    path('share/<uuid:post_id>/', views.share_post, name='share_post'),
    path('edit/<uuid:post_id>/', views.edit_post, name='edit_post'),
    path('delete/<uuid:post_id>/', views.delete_post, name='delete_post'),
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    
    # Post views
    path('modal/<uuid:post_id>/', views.view_post_modal, name='post_modal'),
    path('detail/<uuid:post_id>/', views.post_detail, name='post_detail'),
    
    # Search
    path('search/', views.search_results, name='search_results'),
    
    # User profile (consider moving to users app)
    path('user/<str:username>/', views.user_profile, name='user_profile'),
]
