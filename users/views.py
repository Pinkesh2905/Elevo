# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.models import User
from django.urls import reverse
from django.http import HttpResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Prefetch, Q
from django.conf import settings
from django.views.decorators.http import require_POST

from .models import (
    EmailChangeToken,
    EmailVerificationToken,
    PasswordResetToken,
    TutorApplication,
    UserProfile,
)
from .forms import (
    SignupForm, UserUpdateForm, UserProfileUpdateForm, CustomLoginForm,
    ForgotPasswordForm, OTPVerificationForm, PasswordResetForm, 
    ResendVerificationForm, EmailChangeForm, TutorApplicationForm
)
from posts.models import Comment, Follow, Post, Repost


# --- Role helper functions ---
def is_student(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'STUDENT'

def is_tutor(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'TUTOR' and user.profile.is_approved_tutor

def is_admin(user):
    return user.is_authenticated and user.is_superuser


def get_or_create_tutor_application(user):
    """
    Fetch tutor application or create an initial draft.
    """
    defaults = {
        'linkedin_url': getattr(user.profile, 'linkedin', '') or '',
        'github_url': getattr(user.profile, 'github', '') or '',
    }
    application, _ = TutorApplication.objects.get_or_create(user=user, defaults=defaults)
    return application


# --- Signup View (Email Verification Removed) ---
def signup(request):
    """
    Handles user registration without email verification.
    Users can login immediately after signup.
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create user and activate immediately
                user = form.save(commit=False)
                user.is_active = True  # Account active immediately
                user.save()

                selected_role = form.cleaned_data.get('role', 'STUDENT')

                # Set up user profile
                if hasattr(user, 'profile'):
                    user.profile.role = selected_role
                    user.profile.is_email_verified = True  # Mark as verified
                    user.profile.save()
                else:
                    UserProfile.objects.create(
                        user=user, 
                        role=selected_role,
                        is_email_verified=True  # Mark as verified
                    )

                # Log the user in immediately
                auth_login(request, user)

                if selected_role == 'TUTOR':
                    get_or_create_tutor_application(user)
                    messages.success(
                        request,
                        (
                            f"Welcome to Elevo, {user.username}. "
                            "Complete your tutor application to start the review process."
                        )
                    )
                    return redirect('users:tutor_application')
                else:
                    messages.success(
                        request,
                        f"Welcome to Elevo, {user.username}! Your account has been created successfully."
                    )
                return redirect('dashboard_redirect')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SignupForm()

    return render(request, 'users/signup.html', {'form': form})


@login_required
def tutor_application(request):
    """
    Tutor onboarding flow for submitting/resubmitting tutor application details.
    """
    if request.user.profile.role != 'TUTOR':
        messages.info(request, "Tutor application is only available for tutor accounts.")
        return redirect('users:profile')

    application = get_or_create_tutor_application(request.user)

    if application.status == TutorApplication.STATUS_APPROVED and not request.user.profile.is_approved_tutor:
        request.user.profile.is_approved_tutor = True
        request.user.profile.save(update_fields=['is_approved_tutor', 'updated_at'])

    if request.method == 'POST':
        form = TutorApplicationForm(request.POST, request.FILES, instance=application)
        submit_action = request.POST.get('submit_action', 'submit')
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user

            if submit_action == 'save_draft':
                app.status = TutorApplication.STATUS_DRAFT
                messages.success(request, "Tutor application saved as draft.")
            else:
                app.status = TutorApplication.STATUS_SUBMITTED
                app.submitted_at = timezone.now()
                app.admin_notes = ""
                app.reviewed_at = None
                app.reviewed_by = None
                request.user.profile.is_approved_tutor = False
                request.user.profile.save(update_fields=['is_approved_tutor', 'updated_at'])
                messages.success(request, "Tutor application submitted for admin review.")

            app.save()

            # Keep profile links in sync.
            request.user.profile.linkedin = app.linkedin_url
            request.user.profile.github = app.github_url
            request.user.profile.save(update_fields=['linkedin', 'github', 'updated_at'])
            return redirect('users:tutor_application')
    else:
        form = TutorApplicationForm(instance=application)

    status_tone = {
        TutorApplication.STATUS_DRAFT: "slate",
        TutorApplication.STATUS_SUBMITTED: "amber",
        TutorApplication.STATUS_UNDER_REVIEW: "sky",
        TutorApplication.STATUS_APPROVED: "emerald",
        TutorApplication.STATUS_REJECTED: "red",
    }.get(application.status, "slate")

    return render(
        request,
        'users/tutor_application.html',
        {
            'application': application,
            'form': form,
            'status_tone': status_tone,
        },
    )


# --- Email Verification Views (Keep for manual verification if needed) ---
def verify_email_sent(request):
    """Show confirmation that verification email was sent."""
    return render(request, 'users/verify_email_sent.html')


def verify_email(request, token):
    """Verify email using token from email link."""
    try:
        verification_token = EmailVerificationToken.objects.get(
            token=token, 
            is_used=False
        )
        
        if verification_token.is_expired():
            messages.error(request, "Verification link has expired. Please request a new one.")
            return redirect('users:resend_verification')
        
        # Activate user account
        user = verification_token.user
        user.is_active = True
        user.save()
        
        # Mark profile as email verified
        user.profile.is_email_verified = True
        user.profile.save()
        
        # Mark token as used
        verification_token.is_used = True
        verification_token.save()
        
        messages.success(request, "Your email has been verified successfully! You can now log in.")
        return redirect('login')
        
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, "Invalid verification link.")
        return redirect('users:resend_verification')


def resend_verification(request):
    """Resend email verification."""
    if request.method == 'POST':
        form = ResendVerificationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Delete old unused tokens
                EmailVerificationToken.objects.filter(user=user, is_used=False).delete()
                
                # Create new token
                token = EmailVerificationToken.objects.create(user=user)
                token.send_verification_email(request)
                
                messages.success(request, f"Verification email sent to {email}")
                return redirect('users:verify_email_sent')
                
            except User.DoesNotExist:
                messages.error(request, "No account found with this email.")
            except Exception as e:
                messages.error(request, "Failed to send verification email. Please try again later.")
    else:
        form = ResendVerificationForm()
    
    return render(request, 'users/resend_verification.html', {'form': form})


# --- Password Reset Views ---
def forgot_password(request):
    """Request password reset."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Delete old unused tokens
                PasswordResetToken.objects.filter(user=user, is_used=False).delete()
                
                # Create new token
                reset_token = PasswordResetToken.objects.create(user=user)
                reset_token.send_reset_email()
                
                # Store token in session for OTP verification
                request.session['reset_token_id'] = reset_token.id
                
                messages.success(request, f"Password reset OTP sent to {email}")
                return redirect('users:verify_otp')
                
            except User.DoesNotExist:
                messages.error(request, "No account found with this email.")
            except Exception as e:
                messages.error(request, "Failed to send reset email. Please try again later.")
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'users/forgot_password.html', {'form': form})


def verify_otp(request):
    """Verify OTP for password reset."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    token_id = request.session.get('reset_token_id')
    if not token_id:
        messages.error(request, "Invalid reset session. Please start over.")
        return redirect('users:forgot_password')
    
    try:
        reset_token = PasswordResetToken.objects.get(id=token_id, is_used=False)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, "Invalid reset token. Please start over.")
        return redirect('users:forgot_password')
    
    if reset_token.is_expired():
        messages.error(request, "Reset token has expired. Please request a new one.")
        return redirect('users:forgot_password')
    
    if reset_token.is_locked():
        messages.error(request, "Too many failed attempts. Please request a new reset.")
        return redirect('users:forgot_password')
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']
            
            if entered_otp == reset_token.otp:
                # OTP correct, proceed to password reset
                request.session['verified_reset_token_id'] = reset_token.id
                return redirect('users:reset_password')
            else:
                reset_token.increment_attempts()
                remaining_attempts = reset_token.MAX_ATTEMPTS - reset_token.attempts
                
                if remaining_attempts > 0:
                    messages.error(request, f"Invalid OTP. {remaining_attempts} attempts remaining.")
                else:
                    messages.error(request, "Too many failed attempts. Please request a new reset.")
                    return redirect('users:forgot_password')
    else:
        form = OTPVerificationForm()
    
    context = {
        'form': form,
        'email': reset_token.user.email,
        'expires_in': (reset_token.expires_at - timezone.now()).total_seconds() / 60,  # minutes
    }
    return render(request, 'users/verify_otp.html', context)


def reset_password(request):
    """Reset password after OTP verification."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    token_id = request.session.get('verified_reset_token_id')
    if not token_id:
        messages.error(request, "Invalid reset session. Please start over.")
        return redirect('users:forgot_password')
    
    try:
        reset_token = PasswordResetToken.objects.get(id=token_id, is_used=False)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, "Invalid reset token. Please start over.")
        return redirect('users:forgot_password')
    
    if reset_token.is_expired():
        messages.error(request, "Reset session has expired. Please start over.")
        return redirect('users:forgot_password')
    
    if request.method == 'POST':
        form = PasswordResetForm(reset_token.user, request.POST)
        if form.is_valid():
            # Save new password
            form.save()
            
            # Mark token as used
            reset_token.is_used = True
            reset_token.save()
            
            # Clear session
            request.session.pop('reset_token_id', None)
            request.session.pop('verified_reset_token_id', None)
            
            messages.success(request, "Password reset successfully! You can now log in with your new password.")
            return redirect('login')
    else:
        form = PasswordResetForm(reset_token.user)
    
    return render(request, 'users/reset_password.html', {'form': form})


# --- Email Change Views ---
@login_required
def change_email(request):
    """Handle email change requests."""
    if request.method == 'POST':
        form = EmailChangeForm(request.user, request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']
            
            # Delete old unused tokens
            EmailChangeToken.objects.filter(user=request.user, is_used=False).delete()
            
            # Create new token
            change_token = EmailChangeToken.objects.create(
                user=request.user,
                new_email=new_email
            )
            
            try:
                change_token.send_change_email(request)
                messages.success(
                    request, 
                    f"Verification email sent to {new_email}. Please check your email to confirm the change."
                )
                return redirect('users:profile')
            except Exception as e:
                messages.error(request, "Failed to send verification email. Please try again later.")
    else:
        form = EmailChangeForm(request.user)
    
    return render(request, 'users/change_email.html', {'form': form})


def verify_email_change(request, token):
    """Verify email change using token from email link."""
    try:
        change_token = EmailChangeToken.objects.get(token=token, is_used=False)
        
        if change_token.is_expired():
            messages.error(request, "Email change link has expired. Please try again.")
            return redirect('users:profile')
        
        # Check if new email is still available
        if User.objects.filter(email=change_token.new_email).exists():
            messages.error(request, "This email is no longer available.")
            return redirect('users:profile')
        
        # Update user email
        user = change_token.user
        user.email = change_token.new_email
        user.save()
        
        # Mark token as used
        change_token.is_used = True
        change_token.save()
        
        messages.success(request, f"Email successfully changed to {change_token.new_email}")
        return redirect('users:profile')
        
    except EmailChangeToken.DoesNotExist:
        messages.error(request, "Invalid email change link.")
        return redirect('users:profile')


# --- Enhanced Login View (Email Verification Check Removed) ---
def custom_login(request):
    """Custom login view without email verification check."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            
            # Login directly without email verification check
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            
            # Redirect to next URL or dashboard
            next_url = request.GET.get('next', 'dashboard_redirect')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid credentials. Please try again.")
    else:
        form = CustomLoginForm()
    
    return render(request, 'registration/login.html', {'form': form})


# --- Logged-in User Profile View ---
@login_required(login_url='login')
def profile(request):
    """
    Displays and updates the logged-in user's profile.
    """
    user_profile = get_object_or_404(UserProfile, user=request.user)
    is_admin_user = is_admin(request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileUpdateForm(request.POST, request.FILES, instance=user_profile)

        # Prevent role or approval changes for non-admins
        if not is_admin_user:
            if 'role' in profile_form.fields:
                del profile_form.fields['role']
            if 'is_approved_tutor' in profile_form.fields:
                del profile_form.fields['is_approved_tutor']

        if user_form.is_valid() and profile_form.is_valid():
            # Check if email is being changed
            old_email = request.user.email
            new_email = user_form.cleaned_data.get('email')
            
            if old_email != new_email:
                # Don't save the user form yet, handle email change separately
                profile_form.save()
                messages.info(
                    request, 
                    "To change your email, please use the 'Change Email' option for security."
                )
                return redirect('users:change_email')
            else:
                user_form.save()
                profile_form.save()
                messages.success(request, "Your profile has been updated successfully!")
                return redirect('users:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileUpdateForm(instance=user_profile)

        if not is_admin_user:
            if 'role' in profile_form.fields:
                del profile_form.fields['role']
            if 'is_approved_tutor' in profile_form.fields:
                del profile_form.fields['is_approved_tutor']

    comment_prefetch = Prefetch(
        'comments',
        queryset=(
            Comment.objects
            .select_related('author', 'author__profile')
            .prefetch_related(
                Prefetch(
                    'replies',
                    queryset=(
                        Comment.objects
                        .select_related('author', 'author__profile')
                    )
                )
            )
            .order_by('created_at')
        )
    )

    user_posts = Post.objects.filter(author=request.user).select_related(
        'author', 'author__profile'
    ).prefetch_related(
        'likes', comment_prefetch, 'reposts', 'shares'
    ).order_by('-created_at')

    followers_count = Follow.objects.filter(following=request.user).count()
    following_count = Follow.objects.filter(follower=request.user).count()

    own_reposts = Repost.objects.filter(user=request.user).select_related(
        'user', 'user__profile', 'original_post', 'original_post__author', 'original_post__author__profile'
    ).prefetch_related(
        'original_post__likes',
        Prefetch(
            'original_post__comments',
            queryset=(
                Comment.objects
                .select_related('author', 'author__profile')
                .prefetch_related(
                    Prefetch(
                        'replies',
                        queryset=(
                            Comment.objects
                            .select_related('author', 'author__profile')
                        )
                    )
                )
                .order_by('created_at')
            )
        ),
        'original_post__reposts',
        'original_post__shares',
    )

    own_activity_items = []
    for post in user_posts:
        own_activity_items.append({
            'type': 'post',
            'post': post,
            'actor': request.user,
            'timestamp': post.created_at,
        })

    for repost in own_reposts:
        own_activity_items.append({
            'type': 'repost',
            'post': repost.original_post,
            'repost': repost,
            'actor': request.user,
            'timestamp': repost.created_at,
        })

    own_activity_items.sort(key=lambda item: item['timestamp'], reverse=True)
    recent_reposts = own_reposts.order_by('-created_at')[:10]

    coding_total = coding_solved = 0
    aptitude_quizzes = aptitude_avg = 0
    try:
        from practice.models import UserProblemProgress
        coding_total = UserProblemProgress.objects.filter(user=request.user).count()
        coding_solved = UserProblemProgress.objects.filter(
            user=request.user, status='solved'
        ).count()
    except Exception:
        pass

    try:
        from aptitude.models import AptitudeQuizAttempt
        quiz_qs = AptitudeQuizAttempt.objects.filter(
            user=request.user, status='completed'
        )
        aptitude_quizzes = quiz_qs.count()
        aptitude_avg = round(
            quiz_qs.aggregate(avg=Avg('score_percent')).get('avg', 0) or 0,
            1
        ) if aptitude_quizzes else 0
    except Exception:
        pass

    tutor_application = None
    if request.user.profile.role == 'TUTOR':
        tutor_application = TutorApplication.objects.filter(user=request.user).first()

    context = {
        'user_profile': user_profile,
        'user_form': user_form,
        'profile_form': profile_form,
        'is_admin_user': is_admin_user,
        'user_posts': user_posts,
        'activity_items': own_activity_items,
        'recent_reposts': recent_reposts,
        'followers_count': followers_count,
        'following_count': following_count,
        'coding_total': coding_total,
        'coding_solved': coding_solved,
        'aptitude_quizzes': aptitude_quizzes,
        'aptitude_avg': aptitude_avg,
        'is_own_profile': True,
        'tutor_application': tutor_application,
    }

    return render(request, 'users/profile.html', context)


# --- Public User Profile View ---
def public_profile(request, username):
    """Public profile view with social timeline and progress insights."""
    user_profile = get_object_or_404(UserProfile, user__username=username)

    comment_prefetch = Prefetch(
        'comments',
        queryset=(
            Comment.objects
            .select_related('author', 'author__profile')
            .prefetch_related(
                Prefetch(
                    'replies',
                    queryset=(
                        Comment.objects
                        .select_related('author', 'author__profile')
                    )
                )
            )
            .order_by('created_at')
        )
    )

    posts = Post.objects.filter(author=user_profile.user).select_related(
        'author', 'author__profile'
    ).prefetch_related('likes', comment_prefetch, 'reposts', 'shares')

    reposts = Repost.objects.filter(user=user_profile.user).select_related(
        'user', 'user__profile', 'original_post', 'original_post__author', 'original_post__author__profile'
    ).prefetch_related(
        'original_post__likes',
        Prefetch(
            'original_post__comments',
            queryset=(
                Comment.objects
                .select_related('author', 'author__profile')
                .prefetch_related(
                    Prefetch(
                        'replies',
                        queryset=(
                            Comment.objects
                            .select_related('author', 'author__profile')
                        )
                    )
                )
                .order_by('created_at')
            )
        ),
        'original_post__reposts',
        'original_post__shares'
    )

    activity_items = []
    for post in posts:
        activity_items.append({
            'type': 'post',
            'post': post,
            'actor': post.author,
            'timestamp': post.created_at,
        })

    for repost in reposts:
        activity_items.append({
            'type': 'repost',
            'post': repost.original_post,
            'repost': repost,
            'actor': repost.user,
            'timestamp': repost.created_at,
        })

    activity_items.sort(key=lambda item: item['timestamp'], reverse=True)

    followers_count = Follow.objects.filter(following=user_profile.user).count()
    following_count = Follow.objects.filter(follower=user_profile.user).count()

    is_own_profile = request.user.is_authenticated and request.user == user_profile.user
    is_following = False
    if request.user.is_authenticated and not is_own_profile:
        is_following = Follow.objects.filter(
            follower=request.user, following=user_profile.user
        ).exists()

    coding_total = coding_solved = coding_attempted = 0
    aptitude_quizzes = aptitude_best = 0
    recent_achievements = []
    try:
        from practice.models import Submission, UserProblemProgress
        coding_total = UserProblemProgress.objects.filter(user=user_profile.user).count()
        coding_solved = UserProblemProgress.objects.filter(
            user=user_profile.user, status='solved'
        ).count()
        coding_attempted = UserProblemProgress.objects.filter(
            user=user_profile.user, status='attempted'
        ).count()
        solved_recent = Submission.objects.filter(
            user=user_profile.user, status='accepted'
        ).select_related('problem').order_by('-created_at')[:4]
        for sub in solved_recent:
            recent_achievements.append({
                'label': 'Solved coding problem',
                'value': sub.problem.title,
                'time': sub.created_at,
            })
    except Exception:
        pass

    try:
        from aptitude.models import AptitudeQuizAttempt
        quiz_qs = AptitudeQuizAttempt.objects.filter(
            user=user_profile.user, status='completed'
        ).order_by('-submitted_at')
        aptitude_quizzes = quiz_qs.count()
        best_quiz = quiz_qs.order_by('-score_percent').first()
        aptitude_best = round(best_quiz.score_percent, 1) if best_quiz else 0
        for quiz in quiz_qs[:4]:
            recent_achievements.append({
                'label': 'Aptitude quiz',
                'value': f"{quiz.correct_answers}/{quiz.total_questions} ({quiz.score_percent:.1f}%)",
                'time': quiz.submitted_at or quiz.started_at,
            })
    except Exception:
        pass

    recent_achievements.sort(key=lambda item: item['time'], reverse=True)
    recent_achievements = recent_achievements[:6]

    context = {
        'user_profile': user_profile,
        'activity_items': activity_items,
        'is_own_profile': is_own_profile,
        'is_following': is_following,
        'followers_count': followers_count,
        'following_count': following_count,
        'coding_total': coding_total,
        'coding_solved': coding_solved,
        'coding_attempted': coding_attempted,
        'aptitude_quizzes': aptitude_quizzes,
        'aptitude_best': aptitude_best,
        'recent_achievements': recent_achievements,
        'is_admin_user': request.user.is_staff,
    }
    return render(request, 'users/view_profile.html', context)


# --- Account Management Views ---
@login_required
def account_settings(request):
    """Account settings page."""
    return render(request, 'users/account_settings.html')


@login_required 
def delete_account(request):
    """Delete user account."""
    if request.method == 'POST':
        password = request.POST.get('password')
        if request.user.check_password(password):
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, "Your account has been deleted successfully.")
            return redirect('home')
        else:
            messages.error(request, "Invalid password.")
    
    return render(request, 'users/delete_account.html')


# --- Admin Views ---
@login_required
def admin_users(request):
    """Admin view to manage users."""
    if not is_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard_redirect')
    
    users = UserProfile.objects.all().select_related('user').order_by('-created_at')
    
    context = {
        'users': users,
    }
    return render(request, 'users/admin_users.html', context)


@login_required
def toggle_user_status(request, user_id):
    """Toggle user active status (admin only)."""
    if not is_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard_redirect')
    
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"User {user.username} has been {status}.")
    
    return redirect('users:admin_users')


@login_required
def approve_tutor(request, user_id):
    """Approve tutor status (admin only)."""
    if not is_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard_redirect')
    
    user_profile = get_object_or_404(UserProfile, user__id=user_id)
    user_profile.is_approved_tutor = not user_profile.is_approved_tutor
    user_profile.save(update_fields=['is_approved_tutor', 'updated_at'])

    application = TutorApplication.objects.filter(user=user_profile.user).first()
    if application:
        if user_profile.is_approved_tutor:
            application.status = TutorApplication.STATUS_APPROVED
            application.reviewed_at = timezone.now()
            application.reviewed_by = request.user
        else:
            application.status = TutorApplication.STATUS_REJECTED
            application.reviewed_at = timezone.now()
            application.reviewed_by = request.user
        application.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'updated_at'])

    status = "approved" if user_profile.is_approved_tutor else "revoked"
    messages.success(request, f"Tutor status {status} for {user_profile.user.username}.")
    
    return redirect('users:admin_users')


# --- Admin Dashboard Views ---
@staff_member_required
def admin_dashboard(request):
    """
    Admin operations dashboard with approvals, platform metrics, and recent activity.
    """
    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)
    month_ago = now - timezone.timedelta(days=30)

    user_qs = User.objects.select_related('profile')
    profile_qs = UserProfile.objects.select_related('user')

    pending_tutor_applications = TutorApplication.objects.filter(
        status__in=[TutorApplication.STATUS_SUBMITTED, TutorApplication.STATUS_UNDER_REVIEW]
    ).select_related('user', 'reviewed_by').order_by('-submitted_at', '-updated_at')

    tutor_status_counts_qs = TutorApplication.objects.values('status').annotate(total=Count('id'))
    tutor_status_counts = {
        TutorApplication.STATUS_DRAFT: 0,
        TutorApplication.STATUS_SUBMITTED: 0,
        TutorApplication.STATUS_UNDER_REVIEW: 0,
        TutorApplication.STATUS_APPROVED: 0,
        TutorApplication.STATUS_REJECTED: 0,
    }
    for row in tutor_status_counts_qs:
        tutor_status_counts[row['status']] = row['total']

    role_counts = {'STUDENT': 0, 'TUTOR': 0, 'ADMIN': 0}
    for row in profile_qs.values('role').annotate(total=Count('id')):
        role_counts[row['role']] = row['total']

    recent_users = user_qs.order_by('-date_joined')[:8]
    stale_users_count = user_qs.filter(
        is_active=True
    ).filter(
        Q(last_login__lt=month_ago) | Q(last_login__isnull=True)
    ).count()

    # Initialize empty defaults for optional app metrics.
    pending_problems = []
    total_problems = active_problems = inactive_problems = 0
    recent_submissions = []
    weekly_submissions = weekly_acceptance_rate = 0
    submission_status_counts = {}

    pending_interview_reviews = []
    pending_interview_reviews_count = 0
    recent_interviews = []
    total_interviews = interviews_this_week = 0
    interview_status_counts = {}

    pending_articles = []

    # Practice app metrics
    try:
        from practice.models import Problem, Submission
        pending_problems = Problem.objects.filter(
            is_active=False
        ).select_related('created_by').prefetch_related('topics', 'companies').order_by('-created_at')
        total_problems = Problem.objects.count()
        active_problems = Problem.objects.filter(is_active=True).count()
        inactive_problems = Problem.objects.filter(is_active=False).count()

        recent_submissions = Submission.objects.select_related(
            'user', 'problem'
        ).order_by('-created_at')[:8]
        weekly_submission_qs = Submission.objects.filter(created_at__gte=week_ago)
        weekly_submissions = weekly_submission_qs.count()
        weekly_accepted = weekly_submission_qs.filter(status='accepted').count()
        weekly_acceptance_rate = round((weekly_accepted / weekly_submissions) * 100, 1) if weekly_submissions else 0
        submission_status_counts = {
            row['status']: row['total']
            for row in weekly_submission_qs.values('status').annotate(total=Count('id'))
        }
    except (ImportError, AttributeError):
        pass

    # Mock interview metrics
    try:
        from mock_interview.models import MockInterviewSession
        pending_interview_reviews = MockInterviewSession.objects.filter(
            status='REVIEW_PENDING'
        ).select_related('user').order_by('-updated_at')
        pending_interview_reviews_count = pending_interview_reviews.count()
        recent_interviews = MockInterviewSession.objects.select_related(
            'user'
        ).order_by('-created_at')[:8]
        total_interviews = MockInterviewSession.objects.count()
        interviews_this_week = MockInterviewSession.objects.filter(created_at__gte=week_ago).count()
        interview_status_counts = {
            row['status']: row['total']
            for row in MockInterviewSession.objects.values('status').annotate(total=Count('id'))
        }
    except (ImportError, AttributeError):
        pass

    # Article moderation metrics (if app exists)
    try:
        from articles.models import Article
        if hasattr(Article, 'status'):
            pending_articles = Article.objects.filter(status='PENDING').select_related('created_by').order_by('-created_at')
        elif hasattr(Article, 'is_active'):
            pending_articles = Article.objects.filter(is_active=False).select_related('created_by').order_by('-created_at')
        elif hasattr(Article, 'is_published'):
            pending_articles = Article.objects.filter(is_published=False).select_related('created_by').order_by('-created_at')
        else:
            pending_articles = Article.objects.all().select_related('created_by').order_by('-created_at')[:10]
    except (ImportError, AttributeError):
        pass

    total_pending_actions = (
        pending_tutor_applications.count()
        + inactive_problems
        + pending_interview_reviews_count
    )

    social_stats = {
        'posts': Post.objects.count(),
        'comments': Comment.objects.count(),
        'follows': Follow.objects.count(),
    }

    context = {
        'pending_tutor_applications': pending_tutor_applications,
        'pending_problems': pending_problems,
        'pending_articles': pending_articles,
        'recent_users': recent_users,
        'recent_submissions': recent_submissions,
        'recent_interviews': recent_interviews,
        'pending_interview_reviews': pending_interview_reviews,
        'social_stats': social_stats,
        'role_counts': role_counts,
        'tutor_status_counts': tutor_status_counts,
        'submission_status_counts': submission_status_counts,
        'interview_status_counts': interview_status_counts,
        'platform_metrics': {
            'total_users': user_qs.count(),
            'active_users': user_qs.filter(is_active=True).count(),
            'inactive_users': user_qs.filter(is_active=False).count(),
            'staff_users': user_qs.filter(is_staff=True).count(),
            'recent_signups': user_qs.filter(date_joined__gte=week_ago).count(),
            'stale_users_count': stale_users_count,
            'approved_tutors': profile_qs.filter(role='TUTOR', is_approved_tutor=True).count(),
            'total_tutors': profile_qs.filter(role='TUTOR').count(),
            'total_problems': total_problems,
            'active_problems': active_problems,
            'inactive_problems': inactive_problems,
            'weekly_submissions': weekly_submissions,
            'weekly_acceptance_rate': weekly_acceptance_rate,
            'total_interviews': total_interviews,
            'interviews_this_week': interviews_this_week,
            'pending_interview_reviews': pending_interview_reviews_count,
            'pending_tutor_reviews': pending_tutor_applications.count(),
            'total_pending_actions': total_pending_actions,
        },
    }

    return render(request, 'users/admin_dashboard.html', context)


@staff_member_required
@require_POST
def admin_approve_tutor(request, user_id):
    """
    Approve a tutor account.
    """
    user = get_object_or_404(User, id=user_id)
    user_profile = user.profile
    application = TutorApplication.objects.filter(user=user).first()

    user_profile.is_approved_tutor = True
    user_profile.save(update_fields=['is_approved_tutor', 'updated_at'])

    if application:
        application.status = TutorApplication.STATUS_APPROVED
        application.admin_notes = (request.POST.get('admin_notes') or '').strip()
        application.reviewed_at = timezone.now()
        application.reviewed_by = request.user
        application.save()

    messages.success(request, f'Tutor {user.username} has been approved successfully!')
    return redirect('users:admin_dashboard')


@staff_member_required
@require_POST
def admin_reject_tutor(request, user_id):
    """
    Reject tutor application and keep tutor account unapproved.
    """
    user = get_object_or_404(User, id=user_id)
    user_profile = user.profile
    application = TutorApplication.objects.filter(user=user).first()

    user_profile.is_approved_tutor = False
    user_profile.save(update_fields=['is_approved_tutor', 'updated_at'])

    if application:
        application.status = TutorApplication.STATUS_REJECTED
        application.admin_notes = (request.POST.get('admin_notes') or '').strip()
        application.reviewed_at = timezone.now()
        application.reviewed_by = request.user
        application.save()

    messages.success(request, f'Tutor application for {user.username} has been rejected.')
    return redirect('users:admin_dashboard')
