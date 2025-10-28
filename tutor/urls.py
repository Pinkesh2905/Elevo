from django.urls import path
from . import views

app_name = 'tutor'

urlpatterns = [
    # ========== TUTOR DASHBOARD ==========
    path('dashboard/', views.tutor_dashboard, name='dashboard'),

    # ========== CONTENT MANAGEMENT (Unified endpoint) ==========
    path('create-update/', views.tutor_content_create_update, name='create_update'),
    
    # ========== PRACTICE PROBLEM MANAGEMENT (AJAX endpoints) ==========
    path('practice-problem/<int:problem_id>/toggle-status/', 
         views.toggle_practice_problem_status, 
         name='toggle_practice_problem_status'),
    
    path('practice-problem/<int:problem_id>/delete/', 
         views.delete_practice_problem, 
         name='delete_practice_problem'),
    
    path('practice-problem/<int:problem_id>/export/', 
         views.export_practice_problem, 
         name='export_practice_problem'),

    # ========== MOCK INTERVIEW REVIEW (Optional - uncomment if needed) ==========
    # path('mock-interviews/reviews/', 
    #      mock_views.tutor_interview_review_list, 
    #      name='mock_interview_review_list'),
    #      
    # path('mock-interviews/reviews/<int:session_id>/', 
    #      mock_views.tutor_review_interview_detail, 
    #      name='mock_interview_review_detail'),
]