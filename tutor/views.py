from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponse
import json
from django.db import models

# Aptitude app models and forms
from aptitude.models import AptitudeCategory, AptitudeTopic, AptitudeProblem, PracticeSet
from aptitude.forms import AptitudeCategoryForm, AptitudeTopicForm, AptitudeProblemForm, PracticeSetForm

# Practice app models and forms
from practice.models import Problem, TestCase, CodeTemplate, Topic, Company, Editorial
from practice.forms import (
    ProblemForm, TestCaseFormSet, CodeTemplateFormSet, EditorialForm, 
    TopicForm, CompanyForm
)

# Mock interview models (if needed)
# from mock_interview.models import MockInterviewSession, InterviewTurn


def is_tutor(user):
    """Check if user is a tutor"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_approved_tutor


def is_tutor_or_admin(user):
    """Check if user is tutor or admin"""
    return user.is_staff or (user.is_authenticated and hasattr(user, 'profile') and user.profile.is_approved_tutor)


@login_required
@user_passes_test(is_tutor, login_url='login')
def tutor_dashboard(request):
    """
    Main tutor dashboard displaying both aptitude and practice problem management.
    """
    # Check if tutor is approved
    if not request.user.profile.is_approved_tutor:
        return render(request, 'tutor/pending_approval.html', {
            "message": "Your tutor account is awaiting admin approval. Please check back later."
        })

    # Get URL parameters for showing specific forms
    show = request.GET.get('show')
    edit_category_id = request.GET.get('edit_category')
    edit_topic_id = request.GET.get('edit_topic')
    edit_aptitude_problem_id = request.GET.get('edit_problem')
    edit_practice_problem_id = request.GET.get('edit_practice_problem')
    edit_practice_set_id = request.GET.get('edit_practice_set')
    edit_coding_topic_id = request.GET.get('edit_coding_topic')
    edit_coding_company_id = request.GET.get('edit_coding_company')

    # Aptitude app data
    categories = AptitudeCategory.objects.all().order_by('name')
    topics = AptitudeTopic.objects.select_related('category').all().order_by('category__name', 'name')
    aptitude_problems = AptitudeProblem.objects.select_related('topic').all().order_by('-created_at')[:10]
    practice_sets = PracticeSet.objects.prefetch_related('problems').all().order_by('-created_at')[:10]

    # Practice app data (coding problems)
    practice_problems = Problem.objects.prefetch_related('topics', 'companies').all().order_by('-created_at')[:10]
    coding_topics = Topic.objects.annotate(
        problem_count=models.Count('problems')
    ).order_by('name')
    coding_companies = Company.objects.annotate(
        problem_count=models.Count('problems')
    ).order_by('name')

    # Statistics
    aptitude_stats = {
        'total_categories': categories.count(),
        'total_topics': topics.count(),
        'total_problems': AptitudeProblem.objects.count(),
        'total_practice_sets': practice_sets.count(),
    }

    practice_stats = {
        'total_problems': Problem.objects.count(),
        'active_problems': Problem.objects.filter(is_active=True).count(),
        'total_topics': coding_topics.count(),
        'total_companies': coding_companies.count(),
    }

    # Initialize forms
    category_form = AptitudeCategoryForm()
    topic_form = AptitudeTopicForm()
    aptitude_problem_form = AptitudeProblemForm()
    practice_set_form = PracticeSetForm()
    
    problem_form = ProblemForm()
    testcase_formset = TestCaseFormSet(prefix='testcases')
    codetemplate_formset = CodeTemplateFormSet(prefix='templates')
    coding_topic_form = TopicForm()
    coding_company_form = CompanyForm()

    # Edit handling - Aptitude
    if edit_category_id:
        category = get_object_or_404(AptitudeCategory, id=edit_category_id)
        category_form = AptitudeCategoryForm(instance=category)
        show = 'category'

    if edit_topic_id:
        topic = get_object_or_404(AptitudeTopic, id=edit_topic_id)
        topic_form = AptitudeTopicForm(instance=topic)
        show = 'topic'

    if edit_aptitude_problem_id:
        problem = get_object_or_404(AptitudeProblem, id=edit_aptitude_problem_id)
        aptitude_problem_form = AptitudeProblemForm(instance=problem)
        show = 'problem'

    if edit_practice_set_id:
        practice_set = get_object_or_404(PracticeSet, id=edit_practice_set_id)
        practice_set_form = PracticeSetForm(instance=practice_set)
        show = 'practice_set'

    # Edit handling - Practice (Coding)
    if edit_practice_problem_id:
        practice_problem = get_object_or_404(Problem, id=edit_practice_problem_id)
        problem_form = ProblemForm(instance=practice_problem)
        testcase_formset = TestCaseFormSet(instance=practice_problem, prefix='testcases')
        codetemplate_formset = CodeTemplateFormSet(instance=practice_problem, prefix='templates')
        show = 'practice_problem'

    if edit_coding_topic_id:
        coding_topic = get_object_or_404(Topic, id=edit_coding_topic_id)
        coding_topic_form = TopicForm(instance=coding_topic)
        show = 'coding_topic'

    if edit_coding_company_id:
        coding_company = get_object_or_404(Company, id=edit_coding_company_id)
        coding_company_form = CompanyForm(instance=coding_company)
        show = 'coding_company'

    context = {
        # Aptitude data
        'categories': categories,
        'topics': topics,
        'aptitude_problems': aptitude_problems,
        'practice_sets': practice_sets,
        'aptitude_stats': aptitude_stats,
        
        # Aptitude forms
        'category_form': category_form,
        'topic_form': topic_form,
        'aptitude_problem_form': aptitude_problem_form,
        'practice_set_form': practice_set_form,
        
        # Practice data
        'practice_problems': practice_problems,
        'coding_topics': coding_topics,
        'coding_companies': coding_companies,
        'practice_stats': practice_stats,
        
        # Practice forms
        'problem_form': problem_form,
        'testcase_formset': testcase_formset,
        'codetemplate_formset': codetemplate_formset,
        'coding_topic_form': coding_topic_form,
        'coding_company_form': coding_company_form,
        
        # UI state
        'show': show,
        'edit_category_id': edit_category_id,
        'edit_topic_id': edit_topic_id,
        'edit_aptitude_problem_id': edit_aptitude_problem_id,
        'edit_practice_problem_id': edit_practice_problem_id,
        'edit_practice_set_id': edit_practice_set_id,
        'edit_coding_topic_id': edit_coding_topic_id,
        'edit_coding_company_id': edit_coding_company_id,
    }

    return render(request, 'tutor/dashboard.html', context)


@login_required
@user_passes_test(is_tutor, login_url='login')
def tutor_content_create_update(request):
    """
    Handle creation/updating of all content types (aptitude + practice).
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('tutor:dashboard')

    content_type = request.POST.get('content_type')

    try:
        with transaction.atomic():
            
            # ========== APTITUDE CONTENT ==========
            if content_type == 'category':
                category_id = request.POST.get('category_id')
                instance = AptitudeCategory.objects.get(id=category_id) if category_id else None
                form = AptitudeCategoryForm(request.POST, instance=instance)
                if form.is_valid():
                    category = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"✅ Category '{category.name}' {action} successfully!")
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Category {field}: {error}")

            elif content_type == 'topic':
                topic_id = request.POST.get('topic_id')
                instance = AptitudeTopic.objects.get(id=topic_id) if topic_id else None
                form = AptitudeTopicForm(request.POST, instance=instance)
                if form.is_valid():
                    topic = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"✅ Topic '{topic.name}' {action} successfully!")
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Topic {field}: {error}")

            elif content_type == 'problem':
                problem_id = request.POST.get('problem_id')
                instance = AptitudeProblem.objects.get(id=problem_id) if problem_id else None
                form = AptitudeProblemForm(request.POST, instance=instance)
                if form.is_valid():
                    problem = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"✅ Aptitude Problem {action} successfully!")
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Problem {field}: {error}")

            elif content_type == 'practice_set':
                practice_set_id = request.POST.get('practice_set_id')
                instance = PracticeSet.objects.get(id=practice_set_id) if practice_set_id else None
                form = PracticeSetForm(request.POST, instance=instance)
                if form.is_valid():
                    practice_set = form.save(commit=False)
                    practice_set.created_by = request.user
                    practice_set.save()
                    form.save_m2m()
                    action = "updated" if instance else "created"
                    messages.success(request, f"✅ Practice Set '{practice_set.title}' {action} successfully!")
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Practice Set {field}: {error}")

            # ========== PRACTICE (CODING) CONTENT ==========
            elif content_type == 'practice_problem':
                practice_problem_id = request.POST.get('practice_problem_id')
                instance = Problem.objects.get(id=practice_problem_id) if practice_problem_id else None
                
                problem_form = ProblemForm(request.POST, instance=instance)
                testcase_formset = TestCaseFormSet(request.POST, instance=instance, prefix='testcases')
                codetemplate_formset = CodeTemplateFormSet(request.POST, instance=instance, prefix='templates')

                if problem_form.is_valid() and testcase_formset.is_valid() and codetemplate_formset.is_valid():
                    practice_problem = problem_form.save(commit=False)
                    practice_problem.created_by = request.user
                    practice_problem.save()
                    problem_form.save_m2m()
                    
                    testcase_formset.instance = practice_problem
                    testcase_formset.save()
                    
                    codetemplate_formset.instance = practice_problem
                    codetemplate_formset.save()
                    
                    action = "updated" if instance else "created"
                    messages.success(request, f"✅ Coding Problem '{practice_problem.title}' {action} successfully!")
                else:
                    if not problem_form.is_valid():
                        for field, errors in problem_form.errors.items():
                            for error in errors:
                                messages.error(request, f"Problem {field}: {error}")
                    
                    if not testcase_formset.is_valid():
                        for form_idx, form in enumerate(testcase_formset):
                            if form.errors:
                                for field, errors in form.errors.items():
                                    messages.error(request, f"Test Case {form_idx + 1} {field}: {error}")
                    
                    if not codetemplate_formset.is_valid():
                        for form_idx, form in enumerate(codetemplate_formset):
                            if form.errors:
                                for field, errors in form.errors.items():
                                    messages.error(request, f"Code Template {form_idx + 1} {field}: {error}")

            elif content_type == 'coding_topic':
                topic_id = request.POST.get('coding_topic_id')
                instance = Topic.objects.get(id=topic_id) if topic_id else None
                form = TopicForm(request.POST, instance=instance)
                if form.is_valid():
                    topic = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"✅ Coding Topic '{topic.name}' {action} successfully!")
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Topic {field}: {error}")

            elif content_type == 'coding_company':
                company_id = request.POST.get('coding_company_id')
                instance = Company.objects.get(id=company_id) if company_id else None
                form = CompanyForm(request.POST, request.FILES, instance=instance)
                if form.is_valid():
                    company = form.save()
                    action = "updated" if instance else "created"
                    messages.success(request, f"✅ Company '{company.name}' {action} successfully!")
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Company {field}: {error}")

            else:
                messages.error(request, "Invalid content type.")
                
    except AptitudeCategory.DoesNotExist:
        messages.error(request, "Category not found.")
    except AptitudeTopic.DoesNotExist:
        messages.error(request, "Aptitude topic not found.")
    except AptitudeProblem.DoesNotExist:
        messages.error(request, "Aptitude problem not found.")
    except PracticeSet.DoesNotExist:
        messages.error(request, "Practice set not found.")
    except Problem.DoesNotExist:
        messages.error(request, "Coding problem not found.")
    except Topic.DoesNotExist:
        messages.error(request, "Coding topic not found.")
    except Company.DoesNotExist:
        messages.error(request, "Company not found.")
    except IntegrityError as e:
        messages.error(request, f"Database error: {e}")
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")

    return redirect('tutor:dashboard')


# ========== PRACTICE PROBLEM AJAX ENDPOINTS ==========

@login_required
@user_passes_test(is_tutor, login_url='login')
def toggle_practice_problem_status(request, problem_id):
    """Toggle practice problem active status (AJAX)"""
    if request.method == 'POST':
        try:
            problem = get_object_or_404(Problem, id=problem_id, created_by=request.user)
            problem.is_active = not problem.is_active
            problem.save()
            
            return JsonResponse({
                'success': True,
                'is_active': problem.is_active,
                'message': f"Problem '{problem.title}' is now {'active' if problem.is_active else 'inactive'}"
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@user_passes_test(is_tutor, login_url='login')
def delete_practice_problem(request, problem_id):
    """Delete a practice problem"""
    problem = get_object_or_404(Problem, id=problem_id, created_by=request.user)
    
    if request.method == 'POST':
        title = problem.title
        problem.delete()
        messages.success(request, f"🗑️ Problem '{title}' deleted successfully!")
        return redirect('tutor:dashboard')
    
    return redirect('tutor:dashboard')


@login_required
@user_passes_test(is_tutor, login_url='login')
def export_practice_problem(request, problem_id):
    """Export practice problem as JSON"""
    problem = get_object_or_404(Problem, id=problem_id, created_by=request.user)
    
    export_data = {
        'problem': {
            'problem_number': problem.problem_number,
            'title': problem.title,
            'difficulty': problem.difficulty,
            'description': problem.description,
            'constraints': problem.constraints,
            'example_input': problem.example_input,
            'example_output': problem.example_output,
            'example_explanation': problem.example_explanation,
            'hints': problem.hints,
            'time_complexity': problem.time_complexity,
            'space_complexity': problem.space_complexity,
            'topics': [topic.name for topic in problem.topics.all()],
            'companies': [company.name for company in problem.companies.all()],
        },
        'test_cases': [
            {
                'input': tc.input_data,
                'output': tc.expected_output,
                'is_sample': tc.is_sample,
                'explanation': tc.explanation,
                'order': tc.order
            }
            for tc in problem.test_cases.all()
        ],
        'code_templates': [
            {
                'language': template.language,
                'template_code': template.template_code,
                'solution_code': template.solution_code
            }
            for template in problem.code_templates.all()
        ]
    }
    
    response = HttpResponse(
        json.dumps(export_data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="problem_{problem.problem_number}_{problem.slug}.json"'
    return response