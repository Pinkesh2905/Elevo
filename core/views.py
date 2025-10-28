from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
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


# --- Homepage View ---
def home(request):
    """
    Role-based homepage:
    - STUDENTS see index.html (homepage)
    - TUTORS and ADMINS are redirected to their dashboards
    """
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        role = request.user.profile.role

        if role == 'TUTOR':
            if request.user.profile.is_approved_tutor:
                return redirect('tutor:dashboard')
            else:
                return render(request, 'tutor/pending_approval.html', {
                    "message": "Your tutor account is awaiting admin approval. Please check back later."
                })

        elif role == 'ADMIN':
            return redirect('practice:admin_dashboard')

    return render(request, 'index.html')


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
    if is_admin(request.user):
        return redirect('practice:admin_dashboard')
    elif is_approved_tutor(request.user):
        return redirect('tutor:dashboard')
    elif is_tutor(request.user) and not request.user.profile.is_approved_tutor:
        return render(request, 'tutor/pending_approval.html', {
            "message": "Your tutor account is awaiting admin approval. Please check back later."
        })
    elif is_student(request.user):
        return redirect('home')

    messages.warning(request, "Your profile is not set up correctly. Contact support.")
    return redirect('home')


# --- Smart Search View ---
def search(request):
    query = request.GET.get('q', '').strip()
    users = courses = posts = []

    if query:
        # Search users by username or name fields
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).select_related('profile')[:5]

        # Search courses by title or description
        courses = Course.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        ).distinct()[:5]

        # Search posts by content, hashtags or author
        posts = Post.objects.filter(
            Q(content__icontains=query) |
            Q(author__username__icontains=query) |
            Q(hashtags__name__icontains=query)
        ).distinct()[:5]

    context = {
        'query': query,
        'users': users,
        'courses': courses,
        'posts': posts,
    }
    return render(request, 'core/search_results.html', context)
