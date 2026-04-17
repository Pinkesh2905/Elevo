from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    # Student Views
    path('', views.assessment_list, name='list'),
    path('attempt/<int:attempt_id>/', views.take_assessment, name='take'),
    path('attempt/<int:attempt_id>/submit/', views.submit_assessment, name='submit'),
    path('attempt/<int:attempt_id>/proctoring/', views.log_proctoring_event, name='log_proctoring'),
    
    # Manager/Admin Views
    path('manage/cohorts/', views.manage_cohorts, name='manage_cohorts'),
    path('manage/cohorts/create/', views.create_cohort, name='create_cohort'),
    path('manage/cohorts/<int:cohort_id>/', views.cohort_detail, name='cohort_detail'),
    
    path('manage/assessments/', views.manage_assessments, name='manage_assessments'),
    path('manage/assessments/create/', views.create_assessment, name='create_assessment'),
    path('manage/assessments/<int:assessment_id>/assign/', views.assign_assessment, name='assign_assessment'),
    
    path('manage/results/<int:assignment_id>/', views.assignment_results, name='assignment_results'),
]
