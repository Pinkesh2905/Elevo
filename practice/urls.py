from django.urls import path
from . import views

app_name = 'practice'

urlpatterns = [
    # Problem browsing
    path('', views.problem_list, name='problem-list'),
    path('problems/', views.problem_list, name='problems'),
    
    # Problem detail and solving - UPDATED TO USE SLUG
    path('problem/<slug:slug>/', views.problem_detail, name='problem_detail'),
    path('problem/<slug:slug>/run/', views.run_code, name='run_code'),
    path('problem/<slug:slug>/submit/', views.submit_code, name='submit_code'),
    
    # Code template AJAX endpoint - UPDATED TO USE SLUG
    path('problem/<slug:slug>/template/', views.get_code_template, name='get_code_template'),
    
    # Editorial/Solution - UPDATED TO USE SLUG
    path('problem/<slug:slug>/editorial/', views.editorial_view, name='editorial'),
    
    # Submissions
    path('submissions/', views.user_submissions, name='user_submissions'),
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    
    # Topics and Companies
    path('topics/', views.topic_list, name='topic_list'),
    path('companies/', views.company_list, name='company_list'),
    
    # Admin actions
    path('admin/activate-problem/<slug:slug>/', views.admin_activate_problem, name='admin_activate_problem'),
]