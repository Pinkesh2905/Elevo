# elevo/users/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import uuid
import secrets
import string
from datetime import timedelta

class UserProfile(models.Model):
    """
    Extends Django's built-in User model to store additional profile information.
    """
    ROLE_CHOICES = [
        ('STUDENT', 'Student'),
        ('TUTOR', 'Tutor'),
        ('ADMIN', 'Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='STUDENT', help_text="Role of the user on the platform.")
    is_approved_tutor = models.BooleanField(default=False, help_text="Designates if a tutor account has been approved by an admin.")
    
    # Email verification
    is_email_verified = models.BooleanField(default=False, help_text="Designates if the user's email has been verified.")
    
    # Profile fields
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, help_text="Profile picture")
    bio = models.TextField(blank=True, null=True, max_length=500, help_text="A short biography about the user.")
    github = models.URLField(blank=True, null=True, help_text="Link to GitHub profile")
    linkedin = models.URLField(blank=True, null=True, help_text="Link to LinkedIn profile")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_role_display(self):
        """Returns the human-readable role."""
        return dict(self.ROLE_CHOICES).get(self.role, self.role)


class EmailVerificationToken(models.Model):
    """
    Model to store email verification tokens.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verification_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Email verification token for {self.user.username}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)  # Token expires in 24 hours
        super().save(*args, **kwargs)
    
    def send_verification_email(self, request):
        """Send verification email to user"""
        subject = 'Verify your Elevo account'
        verification_url = request.build_absolute_uri(f'/users/verify-email/{self.token}/')
        
        html_message = render_to_string('users/emails/verification_email.html', {
            'user': self.user,
            'verification_url': verification_url,
        })
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.user.email],
            html_message=html_message,
            fail_silently=False,
        )


class PasswordResetToken(models.Model):
    """
    Model to store password reset tokens with OTP.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)  # Track failed attempts
    
    MAX_ATTEMPTS = 5
    
    def __str__(self):
        return f"Password reset token for {self.user.username}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def is_locked(self):
        return self.attempts >= self.MAX_ATTEMPTS
    
    def increment_attempts(self):
        self.attempts += 1
        self.save()
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        if not self.otp:
            self.otp = ''.join(secrets.choice(string.digits) for _ in range(6))
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)  # OTP expires in 15 minutes
        super().save(*args, **kwargs)
    
    def send_reset_email(self):
        """Send password reset email with OTP"""
        subject = 'Reset your Elevo password'
        
        html_message = render_to_string('users/emails/password_reset_email.html', {
            'user': self.user,
            'otp': self.otp,
        })
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.user.email],
            html_message=html_message,
            fail_silently=False,
        )


class EmailChangeToken(models.Model):
    """
    Model to handle email change requests with verification.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_change_tokens')
    new_email = models.EmailField()
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Email change token for {self.user.username} to {self.new_email}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=2)  # Token expires in 2 hours
        super().save(*args, **kwargs)
    
    def send_change_email(self, request):
        """Send email change verification to new email"""
        subject = 'Verify your new email for Elevo'
        verification_url = request.build_absolute_uri(f'/users/verify-email-change/{self.token}/')
        
        html_message = render_to_string('users/emails/email_change_verification.html', {
            'user': self.user,
            'new_email': self.new_email,
            'verification_url': verification_url,
        })
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.new_email],
            html_message=html_message,
            fail_silently=False,
        )


# --- Signals to create and save UserProfile automatically ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal receiver to create a UserProfile whenever a new User is created.
    """
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal receiver to save the UserProfile whenever the User is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()