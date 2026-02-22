import random
from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    AptitudeCategory,
    AptitudeProblem,
    AptitudeQuizAttempt,
    AptitudeQuizResponse,
)

QUIZ_QUESTION_COUNT = 30
QUIZ_DURATION_MINUTES = 30


def _achievement_label(score_percent):
    if score_percent >= 90:
        return "Aptitude Ace"
    if score_percent >= 75:
        return "Sharp Solver"
    if score_percent >= 60:
        return "Consistent Learner"
    return "Keep Practicing"


def _ordered_quiz_problems(question_ids):
    problems = AptitudeProblem.objects.select_related("topic", "topic__category").filter(id__in=question_ids)
    problem_map = {p.id: p for p in problems}
    return [problem_map[qid] for qid in question_ids if qid in problem_map]


@transaction.atomic
def _finalize_attempt(attempt, answers, force_expired=False):
    if attempt.status != "in_progress":
        return attempt

    valid_options = {"A", "B", "C", "D"}

    AptitudeQuizResponse.objects.filter(attempt=attempt).delete()

    attempted = 0
    correct = 0
    total = len(attempt.question_ids)

    for problem in _ordered_quiz_problems(attempt.question_ids):
        selected = answers.get(f"question_{problem.id}")
        if selected not in valid_options:
            selected = None

        response = AptitudeQuizResponse.objects.create(
            attempt=attempt,
            problem=problem,
            selected_option=selected,
        )

        if selected:
            attempted += 1
            if response.is_correct:
                correct += 1

    score = round((correct / total) * 100, 2) if total else 0.0

    attempt.total_questions = total
    attempt.attempted_questions = attempted
    attempt.correct_answers = correct
    attempt.score_percent = score
    attempt.achievement_label = _achievement_label(score)
    attempt.submitted_at = timezone.now()
    attempt.status = "expired" if force_expired else "completed"
    attempt.save()

    return attempt


def aptitude_dashboard(request):
    """
    Single home page for aptitude prep + quiz insights.
    """
    categories = AptitudeCategory.objects.prefetch_related("topics").all()
    total_questions_pool = AptitudeProblem.objects.count()

    context = {
        "categories": categories,
        "total_questions_pool": total_questions_pool,
        "quiz_question_count": QUIZ_QUESTION_COUNT,
        "quiz_duration_minutes": QUIZ_DURATION_MINUTES,
    }

    if request.user.is_authenticated:
        completed_attempts = AptitudeQuizAttempt.objects.filter(
            user=request.user,
            status__in=["completed", "expired"],
        )
        recent_attempts = completed_attempts.order_by("-started_at")[:8]

        attempts_count = completed_attempts.count()
        total_answered = sum(a.attempted_questions for a in completed_attempts)
        total_correct = sum(a.correct_answers for a in completed_attempts)
        avg_score = round(sum(a.score_percent for a in completed_attempts) / attempts_count, 2) if attempts_count else 0
        best_score = max((a.score_percent for a in completed_attempts), default=0)

        category_accuracy = []
        per_category = defaultdict(lambda: {"attempted": 0, "correct": 0})

        responses = AptitudeQuizResponse.objects.filter(
            attempt__user=request.user,
            attempt__status__in=["completed", "expired"],
            selected_option__isnull=False,
        ).select_related("problem__topic__category")

        for r in responses:
            cname = r.problem.topic.category.name
            per_category[cname]["attempted"] += 1
            if r.is_correct:
                per_category[cname]["correct"] += 1

        for cname, stats in sorted(per_category.items()):
            attempted = stats["attempted"]
            correct = stats["correct"]
            category_accuracy.append({
                "name": cname,
                "attempted": attempted,
                "correct": correct,
                "accuracy": round((correct / attempted) * 100, 2) if attempted else 0,
            })

        context.update(
            {
                "attempts_count": attempts_count,
                "total_answered": total_answered,
                "total_correct": total_correct,
                "avg_score": avg_score,
                "best_score": best_score,
                "recent_attempts": recent_attempts,
                "category_accuracy": category_accuracy,
            }
        )

    return render(request, "aptitude/dashboard.html", context)


@login_required
def start_quiz(request):
    """
    Start a fresh timed random quiz.
    """
    if request.method != "POST":
        return redirect("aptitude:dashboard")

    existing_attempt = (
        AptitudeQuizAttempt.objects.filter(user=request.user, status="in_progress")
        .order_by("-started_at")
        .first()
    )
    if existing_attempt:
        return redirect("aptitude:quiz_session", attempt_id=existing_attempt.id)

    all_ids = list(AptitudeProblem.objects.values_list("id", flat=True))
    if not all_ids:
        messages.error(request, "No aptitude questions are available yet.")
        return redirect("aptitude:dashboard")

    # Balanced category sampling for realistic placement-like coverage.
    category_map = defaultdict(list)
    for q in AptitudeProblem.objects.select_related("topic__category").only("id", "topic__category__name"):
        category_map[q.topic.category.name].append(q.id)

    categories = list(category_map.keys())
    target = min(QUIZ_QUESTION_COUNT, len(all_ids))
    selected_ids = []
    used = set()

    if categories:
        min_per_category = max(1, target // (2 * len(categories)))
        for cname in categories:
            pool = category_map[cname]
            take = min(min_per_category, len(pool))
            picked = random.sample(pool, take) if take > 0 else []
            for pid in picked:
                if pid not in used:
                    used.add(pid)
                    selected_ids.append(pid)

    remaining = [pid for pid in all_ids if pid not in used]
    if len(selected_ids) < target and remaining:
        extra = random.sample(remaining, min(target - len(selected_ids), len(remaining)))
        selected_ids.extend(extra)

    attempt = AptitudeQuizAttempt.objects.create(
        user=request.user,
        duration_minutes=QUIZ_DURATION_MINUTES,
        question_ids=selected_ids,
        total_questions=len(selected_ids),
        status="in_progress",
    )

    return redirect("aptitude:quiz_session", attempt_id=attempt.id)


@login_required
def quiz_session(request, attempt_id):
    """
    Render and submit the timed quiz session.
    """
    attempt = get_object_or_404(AptitudeQuizAttempt, id=attempt_id, user=request.user)

    if attempt.status != "in_progress":
        return redirect("aptitude:quiz_result", attempt_id=attempt.id)

    deadline = attempt.started_at + timedelta(minutes=attempt.duration_minutes)
    remaining_seconds = int((deadline - timezone.now()).total_seconds())

    if request.method == "POST":
        force_expired = timezone.now() > deadline
        _finalize_attempt(attempt, request.POST, force_expired=force_expired)
        return redirect("aptitude:quiz_result", attempt_id=attempt.id)

    if remaining_seconds <= 0:
        _finalize_attempt(attempt, {}, force_expired=True)
        return redirect("aptitude:quiz_result", attempt_id=attempt.id)

    questions = _ordered_quiz_problems(attempt.question_ids)

    return render(
        request,
        "aptitude/quiz_session.html",
        {
            "attempt": attempt,
            "questions": questions,
            "remaining_seconds": remaining_seconds,
        },
    )


@login_required
def quiz_result(request, attempt_id):
    """
    Show one attempt result with question-level review and insights.
    """
    attempt = get_object_or_404(
        AptitudeQuizAttempt.objects.select_related("user"),
        id=attempt_id,
        user=request.user,
    )

    responses = (
        AptitudeQuizResponse.objects.filter(attempt=attempt)
        .select_related("problem__topic__category")
        .order_by("problem_id")
    )

    category_summary = defaultdict(lambda: {"attempted": 0, "correct": 0})
    for r in responses:
        cname = r.problem.topic.category.name
        if r.selected_option:
            category_summary[cname]["attempted"] += 1
            if r.is_correct:
                category_summary[cname]["correct"] += 1

    insights = []
    for cname, stats in sorted(category_summary.items()):
        attempted = stats["attempted"]
        correct = stats["correct"]
        insights.append(
            {
                "name": cname,
                "attempted": attempted,
                "correct": correct,
                "accuracy": round((correct / attempted) * 100, 2) if attempted else 0,
            }
        )

    return render(
        request,
        "aptitude/quiz_result.html",
        {
            "attempt": attempt,
            "responses": responses,
            "insights": insights,
        },
    )


@login_required
def quiz_history(request):
    attempts = AptitudeQuizAttempt.objects.filter(
        user=request.user,
        status__in=["completed", "expired"],
    ).order_by("-started_at")

    return render(request, "aptitude/quiz_history.html", {"attempts": attempts})


# -----------------------------------------------------------------
# Legacy routes: keep URL compatibility but reduce page sprawl.
# -----------------------------------------------------------------


def topic_list(request, category_id):
    messages.info(request, "Topic pages were consolidated. Use the Aptitude dashboard filters and quiz flow.")
    return redirect("aptitude:dashboard")


def problem_list(request, topic_id):
    messages.info(request, "Problem list pages were consolidated into the main Aptitude flow.")
    return redirect("aptitude:dashboard")


@login_required
def problem_detail(request, problem_id):
    messages.info(request, "Single problem pages were replaced by the timed quiz flow.")
    return redirect("aptitude:dashboard")


@login_required
def practice_set_detail(request, set_id):
    messages.info(request, "Practice sets were replaced by random timed quizzes.")
    return redirect("aptitude:dashboard")


@login_required
def practice_set_result(request, set_id):
    messages.info(request, "Practice set results were consolidated into quiz results.")
    return redirect("aptitude:dashboard")


@login_required
def user_progress(request):
    return redirect("aptitude:quiz_history")
