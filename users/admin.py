# elevo/users/admin.py
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    EmailChangeToken,
    EmailVerificationToken,
    PasswordResetToken,
    TutorApplication,
    UserProfile,
)


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('role', 'is_approved_tutor', 'is_email_verified', 'avatar', 'bio', 'github', 'linkedin')
    readonly_fields = ('created_at', 'updated_at')


class UserAdmin(BaseUserAdmin):
    """Enhanced User admin with profile inline."""
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_role', 'get_email_verified', 'get_tutor_approved', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'profile__role', 'profile__is_approved_tutor', 'profile__is_email_verified')
    search_fields = ('username', 'email', 'profile__bio')
    actions = ['verify_emails', 'approve_tutors', 'activate_users', 'deactivate_users']
    
    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else 'No Profile'
    get_role.short_description = 'Role'
    get_role.admin_order_field = 'profile__role'
    
    def get_email_verified(self, obj):
        if hasattr(obj, 'profile'):
            if obj.profile.is_email_verified:
                return format_html('<span style="color: green;">✓ Verified</span>')
            else:
                return format_html('<span style="color: red;">✗ Not Verified</span>')
        return 'No Profile'
    get_email_verified.short_description = 'Email Status'
    get_email_verified.admin_order_field = 'profile__is_email_verified'
    
    def get_tutor_approved(self, obj):
        if hasattr(obj, 'profile') and obj.profile.role == 'TUTOR':
            if obj.profile.is_approved_tutor:
                return format_html('<span style="color: green;">✓ Approved</span>')
            else:
                return format_html('<span style="color: orange;">⏳ Pending</span>')
        return 'N/A'
    get_tutor_approved.short_description = 'Tutor Status'
    get_tutor_approved.admin_order_field = 'profile__is_approved_tutor'
    
    def verify_emails(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile'):
                user.profile.is_email_verified = True
                user.profile.save()
                count += 1
        self.message_user(request, f'{count} users email verification status updated.')
    verify_emails.short_description = 'Mark selected users as email verified'
    
    def approve_tutors(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile') and user.profile.role == 'TUTOR':
                user.profile.is_approved_tutor = True
                user.profile.save()
                count += 1
        self.message_user(request, f'{count} tutors approved.')
    approve_tutors.short_description = 'Approve selected tutors'
    
    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} users activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} users deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_approved_tutor', 'is_email_verified', 'created_at')
    list_filter = ('role', 'is_approved_tutor', 'is_email_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'bio')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('user', 'role', 'is_approved_tutor', 'is_email_verified', 'avatar', 'bio', 'github', 'linkedin', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(TutorApplication)
class TutorApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'years_experience', 'submitted_at', 'reviewed_at', 'reviewed_by')
    list_filter = ('status', 'submitted_at', 'reviewed_at')
    search_fields = ('user__username', 'user__email', 'headline', 'expertise_areas')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'reviewed_at')
    fieldsets = (
        ('Applicant', {'fields': ('user', 'status')}),
        ('Profile', {'fields': ('headline', 'expertise_areas', 'years_experience', 'current_organization')}),
        ('Details', {'fields': ('motivation', 'teaching_experience', 'linkedin_url', 'github_url', 'portfolio_url', 'resume')}),
        ('Review', {'fields': ('admin_notes', 'reviewed_by', 'submitted_at', 'reviewed_at')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_preview', 'created_at', 'expires_at', 'is_used', 'is_expired_status')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('token', 'created_at', 'expires_at', 'is_expired_status')
    ordering = ('-created_at',)
    
    def token_preview(self, obj):
        return f"{obj.token[:8]}...{obj.token[-8:]}"
    token_preview.short_description = 'Token'
    
    def is_expired_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        else:
            return format_html('<span style="color: green;">Valid</span>')
    is_expired_status.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_preview', 'otp', 'created_at', 'expires_at', 'is_used', 'attempts', 'is_expired_status')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'token', 'otp')
    readonly_fields = ('token', 'otp', 'created_at', 'expires_at', 'is_expired_status', 'is_locked_status')
    ordering = ('-created_at',)
    
    def token_preview(self, obj):
        return f"{obj.token[:8]}...{obj.token[-8:]}"
    token_preview.short_description = 'Token'
    
    def is_expired_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        elif obj.is_locked():
            return format_html('<span style="color: orange;">Locked</span>')
        else:
            return format_html('<span style="color: green;">Valid</span>')
    is_expired_status.short_description = 'Status'
    
    def is_locked_status(self, obj):
        if obj.is_locked():
            return format_html('<span style="color: red;">Locked (too many attempts)</span>')
        else:
            remaining = obj.MAX_ATTEMPTS - obj.attempts
            return format_html(f'<span style="color: green;">{remaining} attempts remaining</span>')
    is_locked_status.short_description = 'Attempts Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(EmailChangeToken)
class EmailChangeTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_email', 'new_email', 'token_preview', 'created_at', 'expires_at', 'is_used', 'is_expired_status')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'new_email', 'token')
    readonly_fields = ('token', 'created_at', 'expires_at', 'is_expired_status', 'current_email')
    ordering = ('-created_at',)
    
    def current_email(self, obj):
        return obj.user.email
    current_email.short_description = 'Current Email'
    
    def token_preview(self, obj):
        return f"{obj.token[:8]}...{obj.token[-8:]}"
    token_preview.short_description = 'Token'
    
    def is_expired_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        else:
            return format_html('<span style="color: green;">Valid</span>')
    is_expired_status.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Admin site customization
admin.site.site_header = 'Elevo Administration'
admin.site.site_title = 'Elevo Admin'
admin.site.index_title = 'Welcome to Elevo Administration'
