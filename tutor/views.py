from urllib.parse import urlencode
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from aptitude.forms import AptitudeCategoryForm, AptitudeProblemForm, AptitudeTopicForm, PracticeSetForm
from aptitude.models import AptitudeCategory, AptitudeProblem, AptitudeTopic, PracticeSet
from mock_interview.models import MockInterviewSession
from practice.forms import CodeTemplateFormSet, CompanyForm, ProblemForm, TestCaseFormSet, TopicForm
from practice.models import Company, Problem, Topic


def is_tutor(user):
    """Check whether user is an approved tutor."""
    return (
        user.is_authenticated
        and hasattr(user, "profile")
        and user.profile.is_approved_tutor
    )


def is_tutor_or_admin(user):
    """Check whether user can access tutor operations."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, "profile") and user.profile.is_approved_tutor


def _redirect_to_dashboard(*, tab="overview", show=None):
    params = {"tab": tab}
    if show:
        params["show"] = show
    return redirect(f"{reverse('tutor:dashboard')}?{urlencode(params)}")


def _show_for_content_type(content_type):
    return {
        "category": "category",
        "topic": "topic",
        "problem": "problem",
        "practice_set": "practice_set",
        "practice_problem": "practice_problem",
        "coding_topic": "coding_topic",
        "coding_company": "coding_company",
    }.get(content_type)


def _tab_for_content_type(content_type):
    if content_type in {"category", "topic", "problem", "practice_set"}:
        return "aptitude"
    if content_type in {"practice_problem", "coding_topic", "coding_company"}:
        return "coding"
    return "overview"


def _emit_form_errors(request, form, prefix):
    for field, errors in form.errors.items():
        field_label = "General" if field == "__all__" else field.replace("_", " ").title()
        for error in errors:
            messages.error(request, f"{prefix} {field_label}: {error}")


@login_required
@user_passes_test(is_tutor_or_admin, login_url="login")
def tutor_dashboard(request):
    """Tutor workspace for aptitude, coding, and interview review operations."""
    if not request.user.is_staff and not request.user.profile.is_approved_tutor:
        return render(
            request,
            "tutor/pending_approval.html",
            {"message": "Your tutor account is awaiting admin approval. Please check back later."},
        )

    selected_tab = request.GET.get("tab", "overview")
    if selected_tab not in {"overview", "aptitude", "coding", "reviews"}:
        selected_tab = "overview"

    show = request.GET.get("show")
    edit_category_id = request.GET.get("edit_category")
    edit_topic_id = request.GET.get("edit_topic")
    edit_aptitude_problem_id = request.GET.get("edit_problem")
    edit_practice_problem_id = request.GET.get("edit_practice_problem")
    edit_practice_set_id = request.GET.get("edit_practice_set")
    edit_coding_topic_id = request.GET.get("edit_coding_topic")
    edit_coding_company_id = request.GET.get("edit_coding_company")

    query = (request.GET.get("q") or "").strip()
    coding_status = request.GET.get("coding_status", "all")
    coding_difficulty = request.GET.get("coding_difficulty", "all")
    review_status = request.GET.get("review_status", "all")

    categories = AptitudeCategory.objects.all().order_by("name")
    topics = AptitudeTopic.objects.select_related("category").order_by("category__name", "name")

    aptitude_problems_qs = AptitudeProblem.objects.select_related("topic", "topic__category")
    if query:
        aptitude_problems_qs = aptitude_problems_qs.filter(
            Q(question_text__icontains=query)
            | Q(topic__name__icontains=query)
            | Q(topic__category__name__icontains=query)
        )
    aptitude_problems = aptitude_problems_qs.order_by("-created_at")[:12]

    practice_sets_qs = PracticeSet.objects.prefetch_related("problems")
    if query:
        practice_sets_qs = practice_sets_qs.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    practice_sets = practice_sets_qs.order_by("-created_at")[:10]

    practice_problems_qs = Problem.objects.prefetch_related("topics", "companies")
    if query:
        practice_problems_qs = practice_problems_qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(slug__icontains=query)
            | Q(problem_number__icontains=query)
            | Q(topics__name__icontains=query)
            | Q(companies__name__icontains=query)
        ).distinct()

    if coding_status == "active":
        practice_problems_qs = practice_problems_qs.filter(is_active=True)
    elif coding_status == "inactive":
        practice_problems_qs = practice_problems_qs.filter(is_active=False)

    if coding_difficulty in {"easy", "medium", "hard"}:
        practice_problems_qs = practice_problems_qs.filter(difficulty=coding_difficulty)

    practice_problems = practice_problems_qs.order_by("-created_at")[:12]

    coding_topics = Topic.objects.annotate(problem_count=Count("problems")).order_by("name")
    coding_companies = Company.objects.annotate(problem_count=Count("problems")).order_by("name")

    review_qs = MockInterviewSession.objects.select_related("user").annotate(
        turn_count=Count("turns"),
        answered_count=Count("turns", filter=Q(turns__user_answer__isnull=False) & ~Q(turns__user_answer="")),
    )
    if review_status in {"STARTED", "COMPLETED", "REVIEW_PENDING", "REVIEWED", "CANCELLED"}:
        review_qs = review_qs.filter(status=review_status)
    if query:
        review_qs = review_qs.filter(
            Q(user__username__icontains=query)
            | Q(job_role__icontains=query)
            | Q(key_skills__icontains=query)
        )
    recent_review_sessions = review_qs.order_by("-updated_at")[:8]

    aptitude_stats = {
        "total_categories": categories.count(),
        "total_topics": topics.count(),
        "total_problems": AptitudeProblem.objects.count(),
        "total_practice_sets": PracticeSet.objects.count(),
    }
    practice_stats = {
        "total_problems": Problem.objects.count(),
        "active_problems": Problem.objects.filter(is_active=True).count(),
        "inactive_problems": Problem.objects.filter(is_active=False).count(),
        "total_topics": coding_topics.count(),
        "total_companies": coding_companies.count(),
    }
    review_stats = {
        "pending": MockInterviewSession.objects.filter(status="REVIEW_PENDING").count(),
        "reviewed": MockInterviewSession.objects.filter(status="REVIEWED").count(),
        "completed": MockInterviewSession.objects.filter(status="COMPLETED").count(),
        "started": MockInterviewSession.objects.filter(status="STARTED").count(),
    }

    category_form = AptitudeCategoryForm()
    topic_form = AptitudeTopicForm()
    aptitude_problem_form = AptitudeProblemForm()
    practice_set_form = PracticeSetForm()

    problem_form = ProblemForm()
    testcase_formset = TestCaseFormSet(prefix="testcases")
    codetemplate_formset = CodeTemplateFormSet(prefix="templates")
    coding_topic_form = TopicForm()
    coding_company_form = CompanyForm()

    if edit_category_id:
        category = get_object_or_404(AptitudeCategory, id=edit_category_id)
        category_form = AptitudeCategoryForm(instance=category)
        show = "category"
        selected_tab = "aptitude"

    if edit_topic_id:
        topic = get_object_or_404(AptitudeTopic, id=edit_topic_id)
        topic_form = AptitudeTopicForm(instance=topic)
        show = "topic"
        selected_tab = "aptitude"

    if edit_aptitude_problem_id:
        problem = get_object_or_404(AptitudeProblem, id=edit_aptitude_problem_id)
        aptitude_problem_form = AptitudeProblemForm(instance=problem)
        show = "problem"
        selected_tab = "aptitude"

    if edit_practice_set_id:
        practice_set = get_object_or_404(PracticeSet, id=edit_practice_set_id)
        practice_set_form = PracticeSetForm(instance=practice_set)
        show = "practice_set"
        selected_tab = "aptitude"

    if edit_practice_problem_id:
        practice_problem = get_object_or_404(Problem, id=edit_practice_problem_id)
        problem_form = ProblemForm(instance=practice_problem)
        testcase_formset = TestCaseFormSet(instance=practice_problem, prefix="testcases")
        codetemplate_formset = CodeTemplateFormSet(instance=practice_problem, prefix="templates")
        show = "practice_problem"
        selected_tab = "coding"

    if edit_coding_topic_id:
        coding_topic = get_object_or_404(Topic, id=edit_coding_topic_id)
        coding_topic_form = TopicForm(instance=coding_topic)
        show = "coding_topic"
        selected_tab = "coding"

    if edit_coding_company_id:
        coding_company = get_object_or_404(Company, id=edit_coding_company_id)
        coding_company_form = CompanyForm(instance=coding_company)
        show = "coding_company"
        selected_tab = "coding"

    context = {
        "categories": categories,
        "topics": topics,
        "aptitude_problems": aptitude_problems,
        "practice_sets": practice_sets,
        "aptitude_stats": aptitude_stats,
        "category_form": category_form,
        "topic_form": topic_form,
        "aptitude_problem_form": aptitude_problem_form,
        "practice_set_form": practice_set_form,
        "practice_problems": practice_problems,
        "coding_topics": coding_topics,
        "coding_companies": coding_companies,
        "practice_stats": practice_stats,
        "problem_form": problem_form,
        "testcase_formset": testcase_formset,
        "codetemplate_formset": codetemplate_formset,
        "coding_topic_form": coding_topic_form,
        "coding_company_form": coding_company_form,
        "show": show,
        "edit_category_id": edit_category_id,
        "edit_topic_id": edit_topic_id,
        "edit_aptitude_problem_id": edit_aptitude_problem_id,
        "edit_practice_problem_id": edit_practice_problem_id,
        "edit_practice_set_id": edit_practice_set_id,
        "edit_coding_topic_id": edit_coding_topic_id,
        "edit_coding_company_id": edit_coding_company_id,
        "selected_tab": selected_tab,
        "search_query": query,
        "coding_status": coding_status,
        "coding_difficulty": coding_difficulty,
        "review_status": review_status,
        "recent_review_sessions": recent_review_sessions,
        "review_stats": review_stats,
    }
    return render(request, "tutor/dashboard.html", context)


@login_required
@user_passes_test(is_tutor_or_admin, login_url="login")
def tutor_content_create_update(request):
    """Create/update aptitude and coding content from one endpoint."""
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return _redirect_to_dashboard()

    content_type = request.POST.get("content_type")
    show = _show_for_content_type(content_type)
    tab = _tab_for_content_type(content_type)

    try:
        with transaction.atomic():
            if content_type == "category":
                category_id = request.POST.get("category_id")
                instance = AptitudeCategory.objects.filter(id=category_id).first() if category_id else None
                form = AptitudeCategoryForm(request.POST, instance=instance)
                if form.is_valid():
                    category = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"Category '{category.name}' {action} successfully.")
                else:
                    _emit_form_errors(request, form, "Category")

            elif content_type == "topic":
                topic_id = request.POST.get("topic_id")
                instance = AptitudeTopic.objects.filter(id=topic_id).first() if topic_id else None
                form = AptitudeTopicForm(request.POST, instance=instance)
                if form.is_valid():
                    topic = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"Topic '{topic.name}' {action} successfully.")
                else:
                    _emit_form_errors(request, form, "Topic")

            elif content_type == "problem":
                problem_id = request.POST.get("problem_id")
                instance = AptitudeProblem.objects.filter(id=problem_id).first() if problem_id else None
                form = AptitudeProblemForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"Aptitude problem {action} successfully.")
                else:
                    _emit_form_errors(request, form, "Aptitude Problem")

            elif content_type == "practice_set":
                practice_set_id = request.POST.get("practice_set_id")
                instance = PracticeSet.objects.filter(id=practice_set_id).first() if practice_set_id else None
                form = PracticeSetForm(request.POST, instance=instance)
                if form.is_valid():
                    practice_set = form.save(commit=False)
                    if not practice_set.created_by_id:
                        practice_set.created_by = request.user
                    practice_set.save()
                    form.save_m2m()
                    action = "updated" if instance else "created"
                    messages.success(request, f"Practice set '{practice_set.title}' {action} successfully.")
                else:
                    _emit_form_errors(request, form, "Practice Set")

            elif content_type == "practice_problem":
                practice_problem_id = request.POST.get("practice_problem_id")
                instance = Problem.objects.filter(id=practice_problem_id).first() if practice_problem_id else None

                problem_form = ProblemForm(request.POST, instance=instance)
                testcase_formset = TestCaseFormSet(request.POST, instance=instance, prefix="testcases")
                codetemplate_formset = CodeTemplateFormSet(request.POST, instance=instance, prefix="templates")

                forms_valid = (
                    problem_form.is_valid()
                    and testcase_formset.is_valid()
                    and codetemplate_formset.is_valid()
                )
                if forms_valid:
                    practice_problem = problem_form.save(commit=False)
                    if not practice_problem.created_by_id:
                        practice_problem.created_by = request.user
                    practice_problem.save()
                    problem_form.save_m2m()

                    testcase_formset.instance = practice_problem
                    testcase_formset.save()

                    codetemplate_formset.instance = practice_problem
                    codetemplate_formset.save()

                    action = "updated" if instance else "created"
                    messages.success(request, f"Coding problem '{practice_problem.title}' {action} successfully.")
                else:
                    if not problem_form.is_valid():
                        _emit_form_errors(request, problem_form, "Coding Problem")
                    for error in testcase_formset.non_form_errors():
                        messages.error(request, f"Test Cases: {error}")
                    for form_idx, form in enumerate(testcase_formset.forms, start=1):
                        if form.errors:
                            for field, errors in form.errors.items():
                                for error in errors:
                                    messages.error(
                                        request,
                                        f"Test Case {form_idx} {field.replace('_', ' ').title()}: {error}",
                                    )
                    for error in codetemplate_formset.non_form_errors():
                        messages.error(request, f"Code Templates: {error}")
                    for form_idx, form in enumerate(codetemplate_formset.forms, start=1):
                        if form.errors:
                            for field, errors in form.errors.items():
                                for error in errors:
                                    messages.error(
                                        request,
                                        f"Template {form_idx} {field.replace('_', ' ').title()}: {error}",
                                    )

            elif content_type == "coding_topic":
                topic_id = request.POST.get("coding_topic_id")
                instance = Topic.objects.filter(id=topic_id).first() if topic_id else None
                form = TopicForm(request.POST, instance=instance)
                if form.is_valid():
                    topic = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"Coding topic '{topic.name}' {action} successfully.")
                else:
                    _emit_form_errors(request, form, "Coding Topic")

            elif content_type == "coding_company":
                company_id = request.POST.get("coding_company_id")
                instance = Company.objects.filter(id=company_id).first() if company_id else None
                form = CompanyForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    company = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"Company '{company.name}' {action} successfully.")
                else:
                    _emit_form_errors(request, form, "Company")

            else:
                messages.error(request, "Invalid content type.")

    except IntegrityError as exc:
        messages.error(request, f"Database error: {exc}")
    except Exception as exc:
        messages.error(request, f"Unexpected error: {exc}")

    return _redirect_to_dashboard(tab=tab, show=show)


@login_required
@user_passes_test(is_tutor_or_admin, login_url="login")
def toggle_practice_problem_status(request, problem_id):
    """Toggle coding problem active state."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request"}, status=405)

    try:
        problem = get_object_or_404(Problem, id=problem_id)
        problem.is_active = not problem.is_active
        problem.save(update_fields=["is_active", "updated_at"])
        return JsonResponse(
            {
                "success": True,
                "is_active": problem.is_active,
                "message": f"Problem '{problem.title}' is now {'active' if problem.is_active else 'inactive'}.",
            }
        )
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@user_passes_test(is_tutor_or_admin, login_url="login")
def delete_practice_problem(request, problem_id):
    """Delete a coding problem."""
    problem = get_object_or_404(Problem, id=problem_id)
    if request.method == "POST":
        title = problem.title
        problem.delete()
        messages.success(request, f"Problem '{title}' deleted successfully.")
    return _redirect_to_dashboard(tab="coding")


@login_required
@user_passes_test(is_tutor_or_admin, login_url="login")
def export_practice_problem(request, problem_id):
    """Export coding problem as JSON."""
    problem = get_object_or_404(Problem, id=problem_id)

    export_data = {
        "problem": {
            "problem_number": problem.problem_number,
            "title": problem.title,
            "difficulty": problem.difficulty,
            "description": problem.description,
            "constraints": problem.constraints,
            "example_input": problem.example_input,
            "example_output": problem.example_output,
            "example_explanation": problem.example_explanation,
            "hints": problem.hints,
            "time_complexity": problem.time_complexity,
            "space_complexity": problem.space_complexity,
            "topics": [topic.name for topic in problem.topics.all()],
            "companies": [company.name for company in problem.companies.all()],
        },
        "test_cases": [
            {
                "input": tc.input_data,
                "output": tc.expected_output,
                "is_sample": tc.is_sample,
                "explanation": tc.explanation,
                "order": tc.order,
            }
            for tc in problem.test_cases.all()
        ],
        "code_templates": [
            {
                "language": template.language,
                "template_code": template.template_code,
                "solution_code": template.solution_code,
            }
            for template in problem.code_templates.all()
        ],
    }

    response = HttpResponse(json.dumps(export_data, indent=2), content_type="application/json")
    response["Content-Disposition"] = (
        f'attachment; filename="problem_{problem.problem_number}_{problem.slug}.json"'
    )
    return response


@login_required
@user_passes_test(is_tutor_or_admin, login_url="login")
def tutor_interview_review_list(request):
    """List interview sessions for tutor review."""
    status_filter = request.GET.get("status", "REVIEW_PENDING")
    search = (request.GET.get("q") or "").strip()

    sessions = MockInterviewSession.objects.select_related("user").annotate(
        turn_count=Count("turns"),
        answered_count=Count("turns", filter=Q(turns__user_answer__isnull=False) & ~Q(turns__user_answer="")),
    )

    if status_filter in {"STARTED", "COMPLETED", "REVIEW_PENDING", "REVIEWED", "CANCELLED"}:
        sessions = sessions.filter(status=status_filter)
    if search:
        sessions = sessions.filter(
            Q(user__username__icontains=search)
            | Q(job_role__icontains=search)
            | Q(key_skills__icontains=search)
        )

    sessions = sessions.order_by("-updated_at", "-created_at")

    status_counts = {
        "all": MockInterviewSession.objects.count(),
        "REVIEW_PENDING": MockInterviewSession.objects.filter(status="REVIEW_PENDING").count(),
        "REVIEWED": MockInterviewSession.objects.filter(status="REVIEWED").count(),
        "COMPLETED": MockInterviewSession.objects.filter(status="COMPLETED").count(),
        "STARTED": MockInterviewSession.objects.filter(status="STARTED").count(),
    }

    return render(
        request,
        "tutor/mock_interview_review_list.html",
        {
            "sessions": sessions,
            "status_filter": status_filter,
            "search_query": search,
            "status_counts": status_counts,
        },
    )


@login_required
@user_passes_test(is_tutor_or_admin, login_url="login")
def tutor_review_interview_detail(request, session_id):
    """Review and update a single interview session."""
    session = get_object_or_404(MockInterviewSession.objects.select_related("user"), id=session_id)
    turns = session.turns.all().order_by("turn_number")

    if request.method == "POST":
        tutor_feedback = (request.POST.get("tutor_feedback") or "").strip()
        tutor_score = (request.POST.get("tutor_score") or "").strip()
        next_status = request.POST.get("status")

        if tutor_feedback:
            session.overall_feedback = tutor_feedback

        if tutor_score:
            try:
                parsed_score = float(tutor_score)
                if parsed_score < 0 or parsed_score > 100:
                    raise ValueError("Score out of range")
                session.score = parsed_score
            except ValueError:
                messages.error(request, "Score must be a number between 0 and 100.")
                return redirect("tutor:mock_interview_review_detail", session_id=session.id)

        if next_status in {"REVIEW_PENDING", "REVIEWED", "COMPLETED"}:
            session.status = next_status

        session.save()
        messages.success(request, "Interview review updated successfully.")
        return redirect("tutor:mock_interview_review_detail", session_id=session.id)

    interview_metrics = {
        "total_questions": turns.count(),
        "answered_questions": turns.filter(user_answer__isnull=False).exclude(user_answer="").count(),
        "duration_minutes": (
            round((session.end_time - session.start_time).total_seconds() / 60, 1)
            if session.start_time and session.end_time
            else None
        ),
    }

    return render(
        request,
        "tutor/mock_interview_review_detail.html",
        {
            "session": session,
            "turns": turns,
            "interview_metrics": interview_metrics,
        },
    )
