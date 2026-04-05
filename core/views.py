from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Q
from django.urls import reverse
from django.contrib.auth.models import User

from users.models import UserProfile
from posts.models import Post

# --- Role Helper Functions ---
def is_student(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'STUDENT'

def is_tutor(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'TUTOR'

def is_approved_tutor(user):
    return is_tutor(user) and user.profile.is_approved_tutor

def is_admin(user):
    return user.is_authenticated and user.is_superuser


from practice.models import Problem, Company
from mock_interview.models import MockInterviewSession
from aptitude.models import AptitudeProblem


def _safe_count(queryset):
    try:
        return queryset.count()
    except (ProgrammingError, OperationalError):
        return 0

# --- Homepage View ---
def home(request):
    """
    Role-based homepage with real statistics:
    - STUDENTS see index.html (homepage)
    - TUTORS and ADMINS are redirected to their dashboards
    """
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        role = request.user.profile.role

        if role == 'TUTOR':
            if request.user.profile.is_approved_tutor:
                return redirect('tutor:dashboard')
            else:
                return redirect('users:tutor_application')

        elif role == 'ADMIN':
            return redirect('users:admin_dashboard')

    # Fetch real statistics for the landing page
    stats = {
        'total_problems': _safe_count(Problem.objects.filter(is_active=True)),
        'total_companies': _safe_count(Company.objects.all()),
        'total_questions': _safe_count(AptitudeProblem.objects.all()),
        'active_users': _safe_count(User.objects.all()),
    }

    return render(request, 'index.html', {'stats': stats})


def landing(request):
    return render(request, 'index.html')


# --- Logout View ---
def custom_logout(request):
    logout(request)
    request.session.flush()
    response = redirect('home')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    messages.success(request, "You have been logged out successfully.")
    return response


# --- Dashboard Redirect ---
@login_required(login_url='login')
def dashboard_redirect(request):
    """
    Role-based redirect after login.
    """
    profile = getattr(request.user, 'profile', None)
    
    # New users go to onboarding first
    if profile and not profile.onboarded and not request.user.is_superuser:
        return redirect('users:onboarding_wizard')

    if is_admin(request.user):
        return redirect('users:admin_dashboard')
    elif is_approved_tutor(request.user):
        return redirect('tutor:dashboard')
    elif is_tutor(request.user) and not request.user.profile.is_approved_tutor:
        return redirect('users:tutor_application')
    elif is_student(request.user):
        return redirect('home')
    elif profile and profile.role == 'ORG_ADMIN':
        return redirect('organizations:dashboard')

    messages.warning(request, "Your profile is not set up correctly. Contact support.")
    return redirect('home')


# --- Smart Search View ---
def search(request):
    query = request.GET.get('q', '').strip()
    users = posts = []

    if query:
        # Search users by username or name fields
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).select_related('profile')[:5]

        # Search posts by content, hashtags or author
        posts = Post.objects.filter(
            Q(content__icontains=query) |
            Q(author__username__icontains=query) |
            Q(hashtags__name__icontains=query)
        ).distinct()[:5]

    context = {
        'query': query,
        'users': users,
        'posts': posts,
    }
    return render(request, 'core/search_results.html', context)


def privacy_policy(request):
    return render(request, "core/legal/privacy_policy.html")


def terms_of_service(request):
    return render(request, "core/legal/terms_of_service.html")


def data_processing_addendum(request):
    return render(request, "core/legal/data_processing_addendum.html")
