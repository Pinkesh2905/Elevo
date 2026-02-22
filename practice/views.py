import json
import ast
import re
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator

from .models import (
    Problem, TestCase, CodeTemplate, Editorial, 
    Submission, UserProblemProgress, Topic, Company
)
from .forms import ProblemFilterForm, CodeSubmissionForm

# Import Django settings
from django.conf import settings

# JDoodle API Configuration
JD_CLIENT_ID = getattr(settings, 'JDOODLE_CLIENT_ID', None)
JD_CLIENT_SECRET = getattr(settings, 'JDOODLE_CLIENT_SECRET', None)
JD_EXECUTE_URL = "https://api.jdoodle.com/v1/execute"


def _parse_structured_value(text):
    """
    Parse output/expected strings into comparable Python values.
    Supports JSON-like and Python-literal-like values.
    """
    value = (text or "").strip()
    if value == "":
        return ""

    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none"}:
        return None

    try:
        return json.loads(value)
    except Exception:
        pass

    try:
        return ast.literal_eval(value)
    except Exception:
        return value


def _is_two_sum_problem(problem):
    """
    Identify Two Sum robustly by canonical number/title/slug.
    """
    if not problem:
        return False
    title = (problem.title or "").strip().lower()
    slug = (problem.slug or "").strip().lower()
    return problem.problem_number == 1 or title == "two sum" or "two-sum" in slug


def _validate_two_sum_output(output, test_input):
    """
    Validate any correct index pair for Two Sum.
    Returns:
      True/False when validation is possible,
      None when input/output cannot be parsed.
    """
    try:
        lines = [ln.strip() for ln in (test_input or "").splitlines() if ln.strip()]
        if len(lines) < 2:
            return None

        nums = _parse_structured_value(lines[0])
        target = _parse_structured_value(lines[1])
        ans = _parse_structured_value(output)

        if not isinstance(nums, list) or len(nums) < 2:
            return None
        if not isinstance(target, int):
            try:
                target = int(target)
            except Exception:
                return None
        if not isinstance(ans, list) or len(ans) != 2:
            return False

        i, j = ans[0], ans[1]
        if not isinstance(i, int) or not isinstance(j, int):
            return False
        if i == j:
            return False
        if i < 0 or j < 0 or i >= len(nums) or j >= len(nums):
            return False

        return nums[i] + nums[j] == target
    except Exception:
        return None


def outputs_match(output, expected, problem=None, test_input=None):
    """
    Compare output and expected values with tolerant normalization.
    """
    if _is_two_sum_problem(problem):
        valid = _validate_two_sum_output(output, test_input)
        if valid is not None:
            return valid

    left = _parse_structured_value(output)
    right = _parse_structured_value(expected)
    return left == right


def _extract_python_function_name(code):
    """
    Return first top-level function name from user code.
    """
    match = re.search(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", code or "", re.MULTILINE)
    return match.group(1) if match else None


def _should_wrap_python_function(code):
    """
    Detect LeetCode-style function-only submissions.
    """
    text = code or ""
    return (
        "def " in text
        and "input(" not in text
        and "sys.stdin" not in text
        and "__name__" not in text
    )


def _build_python_harness(code, stdin):
    """
    Wrap function-only Python submissions so students only fill the placeholder.
    Reads each stdin line as one argument and prints normalized output.
    """
    fn_name = _extract_python_function_name(code)
    if not fn_name:
        return code

    stdin_literal = repr(stdin or "")
    harness = f"""

import ast as __ast
import json as __json

def __parse_arg(__line):
    __line = (__line or "").strip()
    if __line == "":
        return ""
    __low = __line.lower()
    if __low == "true":
        return True
    if __low == "false":
        return False
    if __low in ("null", "none"):
        return None
    try:
        return __json.loads(__line)
    except Exception:
        pass
    try:
        return __ast.literal_eval(__line)
    except Exception:
        return __line

__raw = {stdin_literal}
__args = [__parse_arg(__ln) for __ln in __raw.splitlines() if __ln.strip() != ""]
__fn = {fn_name}

try:
    __result = __fn(*__args)
except TypeError:
    __result = __fn(__args)

if isinstance(__result, bool):
    print("true" if __result else "false")
elif __result is None:
    print("null")
elif isinstance(__result, (list, dict)):
    print(__json.dumps(__result, separators=(",", ":")))
else:
    print(__result)
"""
    return (code or "") + harness


def problem_list(request):
    """
    Display list of all problems with filtering and search
    """
    problems = Problem.objects.filter(is_active=True).prefetch_related(
        'topics', 'companies'
    ).select_related('created_by')
    
    # Apply filters
    filter_form = ProblemFilterForm(request.GET)
    
    if filter_form.is_valid():
        # Difficulty filter
        difficulty = filter_form.cleaned_data.get('difficulty')
        if difficulty:
            problems = problems.filter(difficulty=difficulty)
        
        # Topic filter
        topic = filter_form.cleaned_data.get('topic')
        if topic:
            problems = problems.filter(topics=topic)
        
        # Company filter
        company = filter_form.cleaned_data.get('company')
        if company:
            problems = problems.filter(companies=company)
        
        # Search filter
        search = filter_form.cleaned_data.get('search')
        if search:
            problems = problems.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(problem_number__icontains=search)
            )
        
        # Status filter (only for authenticated users)
        if request.user.is_authenticated:
            status = filter_form.cleaned_data.get('status')
            if status:
                user_progress = UserProblemProgress.objects.filter(
                    user=request.user, status=status
                ).values_list('problem_id', flat=True)
                problems = problems.filter(id__in=user_progress)
    
    # Get user progress for authenticated users
    user_progress = {}
    if request.user.is_authenticated:
        progress_qs = UserProblemProgress.objects.filter(
            user=request.user,
            problem__in=problems
        ).select_related('problem')
        user_progress = {p.problem_id: p.status for p in progress_qs}
    
    # Pagination
    paginator = Paginator(problems, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Add progress status to each problem
    for problem in page_obj:
        problem.user_status = user_progress.get(problem.id, 'not_attempted')
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_problems': problems.count(),
    }
    
    return render(request, 'practice/problem_list.html', context)


def problem_detail(request, slug):
    """
    Display problem details and code editor
    UPDATED: Now uses slug instead of problem_id
    """
    problem = get_object_or_404(
        Problem.objects.prefetch_related(
            'topics', 'companies', 
            Prefetch('test_cases', queryset=TestCase.objects.filter(is_sample=True)),
            'code_templates'
        ),
        slug=slug,
        is_active=True
    )
    
    # Get user progress
    user_progress = None
    user_submissions = []
    if request.user.is_authenticated:
        user_progress, _ = UserProblemProgress.objects.get_or_create(
            user=request.user,
            problem=problem
        )
        user_submissions = Submission.objects.filter(
            user=request.user,
            problem=problem
        ).order_by('-created_at')[:10]
    
    # Get default code template (prefer Python)
    default_language = request.GET.get('lang', 'python3')
    code_template = problem.code_templates.filter(language=default_language).first()
    if not code_template:
        code_template = problem.code_templates.first()
    
    # Get available languages for this problem
    # available_languages = problem.code_templates.values_list('language', flat=True)
    
    # Get available languages for this problem
    available_languages = [
        (template.language, template.get_language_display()) 
        for template in problem.code_templates.all()
    ]
    
    context = {
        'problem': problem,
        'user_progress': user_progress,
        'user_submissions': user_submissions,
        'code_template': code_template,
        'available_languages': available_languages,
        'sample_test_cases': problem.test_cases.filter(is_sample=True),
    }
    
    return render(request, 'practice/problem_detail.html', context)


@login_required
def run_code(request, slug):
    """
    Run code against sample test cases (AJAX endpoint)
    UPDATED: Now uses slug instead of problem_id
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    problem = get_object_or_404(Problem, slug=slug, is_active=True)
    
    code = request.POST.get('code', '')
    language = request.POST.get('language', 'python3')
    
    if not code:
        return JsonResponse({'error': 'No code provided'}, status=400)
    
    # Get only sample test cases for "Run Code"
    test_cases = problem.test_cases.filter(is_sample=True)
    
    if not test_cases.exists():
        return JsonResponse({'error': 'No sample test cases available'}, status=400)
    
    # Update user progress
    user_progress, _ = UserProblemProgress.objects.get_or_create(
        user=request.user,
        problem=problem
    )
    if user_progress.status == 'not_attempted':
        user_progress.status = 'attempted'
        user_progress.save()
    
    # Execute code against test cases
    results = []
    all_passed = True
    
    for tc in test_cases:
        result = execute_code_jdoodle(code, language, tc.input_data)
        
        if result['error']:
            return JsonResponse({
                'error': result['error'],
                'details': result.get('details', '')
            }, status=500)
        
        output = result['output']
        expected = tc.expected_output.strip()
        passed = outputs_match(output, expected, problem=problem, test_input=tc.input_data)
        
        if not passed:
            all_passed = False
        
        results.append({
            'input': tc.input_data,
            'expected': expected,
            'output': output,
            'passed': passed,
            'explanation': tc.explanation
        })
    
    return JsonResponse({
        'success': True,
        'all_passed': all_passed,
        'results': results,
        'message': 'All test cases passed!' if all_passed else 'Some test cases failed'
    })


@login_required
def submit_code(request, slug):
    """
    Submit code and run against all test cases (AJAX endpoint)
    UPDATED: Now uses slug instead of problem_id
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    problem = get_object_or_404(Problem, slug=slug, is_active=True)
    
    code = request.POST.get('code', '')
    language = request.POST.get('language', 'python3')
    
    if not code:
        return JsonResponse({'error': 'No code provided'}, status=400)
    
    # Get ALL test cases (including hidden ones)
    test_cases = problem.test_cases.all()
    
    if not test_cases.exists():
        return JsonResponse({'error': 'No test cases available'}, status=400)
    
    # Create submission record
    submission = Submission.objects.create(
        problem=problem,
        user=request.user,
        code=code,
        language=language,
        status='running',
        total_test_cases=test_cases.count()
    )
    
    # Update user progress attempts
    user_progress, _ = UserProblemProgress.objects.get_or_create(
        user=request.user,
        problem=problem
    )
    user_progress.attempts += 1
    if user_progress.status == 'not_attempted':
        user_progress.status = 'attempted'
    user_progress.save()
    
    # Execute code against all test cases
    passed_count = 0
    failed_test_case = None
    error_occurred = False
    error_message = ''
    
    for idx, tc in enumerate(test_cases):
        result = execute_code_jdoodle(code, language, tc.input_data)
        
        if result['error']:
            error_occurred = True
            error_message = result['error']
            if 'compilation' in result['error'].lower():
                submission.status = 'compilation_error'
            elif 'timeout' in result['error'].lower() or 'time limit' in result['error'].lower():
                submission.status = 'time_limit_exceeded'
            else:
                submission.status = 'runtime_error'
            submission.error_message = error_message
            break
        
        output = result['output']
        expected = tc.expected_output.strip()
        
        if outputs_match(output, expected, problem=problem, test_input=tc.input_data):
            passed_count += 1
        else:
            if not failed_test_case:
                failed_test_case = {
                    'test_case_number': idx + 1,
                    'input': tc.input_data if tc.is_sample else 'Hidden',
                    'expected': expected if tc.is_sample else 'Hidden',
                    'output': output,
                    'is_sample': tc.is_sample
                }
    
    # Update submission results
    submission.passed_test_cases = passed_count
    
    if not error_occurred:
        if passed_count == test_cases.count():
            submission.status = 'accepted'
            
            # Update user progress to solved
            if user_progress.status != 'solved':
                user_progress.status = 'solved'
                user_progress.first_solved = timezone.now()
            
            # Update problem statistics
            problem.total_accepted += 1
        else:
            submission.status = 'wrong_answer'
    
    # Update problem statistics
    problem.total_submissions += 1
    problem.save()
    user_progress.save()
    submission.save()
    
    # Prepare response
    response_data = {
        'success': True,
        'submission_id': submission.id,
        'status': submission.status,
        'status_display': submission.get_status_display(),
        'passed_test_cases': passed_count,
        'total_test_cases': test_cases.count(),
        'accepted': submission.status == 'accepted'
    }
    
    if submission.status == 'accepted':
        response_data['message'] = '🎉 Accepted! All test cases passed!'
    elif submission.status == 'wrong_answer' and failed_test_case:
        response_data['message'] = f'Wrong Answer on test case {failed_test_case["test_case_number"]}'
        response_data['failed_test_case'] = failed_test_case
    elif error_occurred:
        response_data['message'] = f'Error: {error_message}'
        response_data['error_message'] = error_message
    
    return JsonResponse(response_data)


def execute_code_jdoodle(code, language, stdin):
    """
    Execute code using JDoodle API
    Returns: {'output': str, 'error': str, 'details': str}
    """
    if not (JD_CLIENT_ID and JD_CLIENT_SECRET):
        return {
            'output': '',
            'error': 'JDoodle credentials not configured',
            'details': ''
        }
    
    script = code
    stdin_value = stdin
    if language == "python3" and _should_wrap_python_function(code):
        script = _build_python_harness(code, stdin)
        # Harness consumes prepared stdin embedded in the script.
        stdin_value = ""

    payload = {
        "clientId": JD_CLIENT_ID,
        "clientSecret": JD_CLIENT_SECRET,
        "script": script,
        "language": language,
        "versionIndex": "0",
        "stdin": stdin_value
    }
    
    try:
        response = requests.post(JD_EXECUTE_URL, json=payload, timeout=15)
    except requests.Timeout:
        return {
            'output': '',
            'error': 'Time Limit Exceeded',
            'details': 'Request timed out after 15 seconds'
        }
    except requests.RequestException as e:
        return {
            'output': '',
            'error': f'Execution error: {str(e)}',
            'details': ''
        }
    
    if response.status_code != 200:
        return {
            'output': '',
            'error': f'JDoodle API error (status {response.status_code})',
            'details': response.text
        }
    
    result = response.json()
    
    # Check for compilation or runtime errors
    if result.get('statusCode') == 1:
        # Compilation error
        return {
            'output': '',
            'error': 'Compilation Error',
            'details': result.get('error', '') or result.get('output', '')
        }
    
    # Check for memory or time limit
    if result.get('memory') and result.get('cpuTime'):
        # These are just informational, we can ignore for now
        pass
    
    output = result.get('output', '') or ''
    
    return {
        'output': output,
        'error': '',
        'details': ''
    }


@login_required
def submission_detail(request, submission_id):
    """
    View details of a specific submission
    """
    submission = get_object_or_404(
        Submission.objects.select_related('problem', 'user'),
        id=submission_id,
        user=request.user
    )
    
    context = {
        'submission': submission,
    }
    
    return render(request, 'practice/submission_detail.html', context)


@login_required
def user_submissions(request):
    """
    List all submissions by the current user
    """
    submissions = Submission.objects.filter(
        user=request.user
    ).select_related('problem').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(submissions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'practice/user_submissions.html', context)


def editorial_view(request, slug):
    """
    View editorial/solution for a problem
    UPDATED: Now uses slug instead of problem_id
    """
    problem = get_object_or_404(Problem, slug=slug, is_active=True)
    
    try:
        editorial = problem.editorial
    except Editorial.DoesNotExist:
        editorial = None
    
    # Check if user has solved the problem or is staff
    can_view = request.user.is_staff
    if request.user.is_authenticated:
        user_progress = UserProblemProgress.objects.filter(
            user=request.user,
            problem=problem,
            status='solved'
        ).exists()
        can_view = can_view or user_progress
    
    context = {
        'problem': problem,
        'editorial': editorial,
        'can_view': can_view,
    }
    
    return render(request, 'practice/editorial.html', context)


def topic_list(request):
    """
    List all topics with problem counts
    """
    topics = Topic.objects.annotate(
        problem_count=Count('problems', filter=Q(problems__is_active=True))
    ).order_by('name')
    
    context = {
        'topics': topics,
    }
    
    return render(request, 'practice/topic_list.html', context)


def company_list(request):
    """
    List all companies with problem counts
    """
    companies = Company.objects.annotate(
        problem_count=Count('problems', filter=Q(problems__is_active=True))
    ).order_by('name')
    
    context = {
        'companies': companies,
    }
    
    return render(request, 'practice/company_list.html', context)


@login_required
def get_code_template(request, slug):
    """
    AJAX endpoint to get code template for a specific language
    UPDATED: Now uses slug instead of problem_id
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=400)
    
    problem = get_object_or_404(Problem, slug=slug, is_active=True)
    language = request.GET.get('language', 'python3')
    
    template = CodeTemplate.objects.filter(
        problem=problem,
        language=language
    ).first()
    
    if not template:
        return JsonResponse({'error': 'Template not found for this language'}, status=404)
    
    return JsonResponse({
        'success': True,
        'template_code': template.template_code,
        'language': template.language
    })

    
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Problem

@staff_member_required
def admin_activate_problem(request, slug):
    """
    Activate a problem (set is_active to True).
    UPDATED: Now uses slug instead of problem_id
    """
    problem = get_object_or_404(Problem, slug=slug)
    problem.is_active = True
    problem.save()
    
    messages.success(request, f'Problem "{problem.title}" has been activated.')
    return redirect('users:admin_dashboard')
