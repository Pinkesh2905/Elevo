from django.urls import path

from . import views

app_name = "mock_interview"

urlpatterns = [
    path("", views.interview_setup, name="interview_setup"),
    path("start/", views.start_mock_interview, name="start_mock_interview"),
    path("<int:session_id>/start/", views.main_interview, name="main_interview"),
    path("<int:session_id>/review/", views.review_interview, name="review_interview"),
    path("<int:session_id>/ai_interaction/", views.ai_interaction_api, name="ai_interaction_api"),
    path("<int:interview_id>/interact/", views.interact_with_ai, name="interact_with_ai"),
    path("<int:session_id>/hints/", views.get_interview_hints_api, name="get_interview_hints_api"),
    path("<int:session_id>/practice-questions/", views.practice_question_api, name="practice_question_api"),
    path("sessions/<int:session_id>/delete/", views.delete_session, name="delete_session"),
    path("sessions/clear-all/", views.clear_all_sessions, name="clear_all_sessions"),
    path("my-interviews/", views.my_mock_interviews, name="my_mock_interviews"),
    path("api/health/", views.ai_health_check, name="ai_health_check"),
    path("delete_session/<int:session_id>/", views.delete_session, name="delete_session_legacy"),
    path("clear_all_sessions/", views.clear_all_sessions, name="clear_all_sessions_legacy"),
    path("<int:session_id>/practice-question/", views.practice_question_api, name="practice_question_legacy"),
]
