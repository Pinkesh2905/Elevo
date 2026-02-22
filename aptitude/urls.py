from django.urls import path
from . import views

app_name = "aptitude"

urlpatterns = [
    # New minimal flow
    path("", views.aptitude_dashboard, name="dashboard"),
    path("start/", views.start_quiz, name="start_quiz"),
    path("quiz/<int:attempt_id>/", views.quiz_session, name="quiz_session"),
    path("result/<int:attempt_id>/", views.quiz_result, name="quiz_result"),
    path("history/", views.quiz_history, name="quiz_history"),

    # Legacy routes (redirected to minimal flow)
    path("category/<int:category_id>/", views.topic_list, name="topic_list"),
    path("topic/<int:topic_id>/", views.problem_list, name="problem_list"),
    path("problem/<int:problem_id>/", views.problem_detail, name="problem_detail"),
    path("practice-set/<int:set_id>/", views.practice_set_detail, name="practice_set_detail"),
    path("practice-set/<int:set_id>/result/", views.practice_set_result, name="practice_set_result"),
    path("progress/", views.user_progress, name="user_progress"),
]
