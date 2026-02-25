from django.contrib import admin
from .models import SubscriptionPlan, Organization, Subscription, Membership, OrgInvitation


class SubscriptionInline(admin.StackedInline):
    model = Subscription
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    readonly_fields = ('joined_at',)
    raw_id_fields = ('user', 'invited_by')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'price_monthly', 'max_students', 'max_problems',
                    'max_interviews_monthly', 'has_editorials', 'is_active')
    list_filter = ('is_active', 'name')
    ordering = ('price_monthly',)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'admin', 'member_count', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'admin__username')
    prepopulated_fields = {'slug': ('name',)}
    raw_id_fields = ('admin',)
    inlines = [SubscriptionInline, MembershipInline]

    def member_count(self, obj):
        return obj.member_count
    member_count.short_description = 'Members'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('organization', 'plan', 'status', 'start_date', 'end_date', 'days_remaining_display')
    list_filter = ('status', 'plan')
    search_fields = ('organization__name',)
    raw_id_fields = ('organization',)
    readonly_fields = ('created_at', 'updated_at')

    def days_remaining_display(self, obj):
        return f"{obj.days_remaining} days"
    days_remaining_display.short_description = 'Remaining'


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active', 'organization')
    search_fields = ('user__username', 'user__email', 'organization__name')
    raw_id_fields = ('user', 'invited_by')


@admin.register(OrgInvitation)
class OrgInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'organization', 'status', 'created_at', 'expires_at')
    list_filter = ('status', 'organization')
    search_fields = ('email', 'organization__name')
    readonly_fields = ('token', 'created_at')
