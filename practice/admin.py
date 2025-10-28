from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Topic, Company, Problem, TestCase, CodeTemplate, 
    Editorial, Submission, UserProblemProgress
)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'problem_count']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    
    def problem_count(self, obj):
        count = obj.problems.count()
        return f"{count} problem{'s' if count != 1 else ''}"
    problem_count.short_description = 'Problems'


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'website_link', 'problem_count']
    search_fields = ['name', 'website']
    prepopulated_fields = {'slug': ('name',)}
    
    def website_link(self, obj):
        if obj.website:
            return format_html('<a href="{}" target="_blank">Visit</a>', obj.website)
        return '-'
    website_link.short_description = 'Website'
    
    def problem_count(self, obj):
        count = obj.problems.count()
        return f"{count} problem{'s' if count != 1 else ''}"
    problem_count.short_description = 'Problems'


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1
    fields = ['input_data', 'expected_output', 'is_sample', 'order']
    ordering = ['order']


class CodeTemplateInline(admin.StackedInline):
    model = CodeTemplate
    extra = 1
    fields = ['language', 'template_code', 'solution_code']


class EditorialInline(admin.StackedInline):
    model = Editorial
    can_delete = False
    fields = ['approach', 'complexity_analysis', 'code_explanation', 'video_url']


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = [
        'problem_number', 'title', 'difficulty_badge', 
        'is_active', 'acceptance_rate_display', 
        'topic_list', 'created_by', 'created_at'
    ]
    list_filter = ['difficulty', 'is_active', 'topics', 'companies', 'created_at']
    search_fields = ['problem_number', 'title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['topics', 'companies']
    readonly_fields = ['created_at', 'updated_at', 'acceptance_rate_display', 'slug']
    
    inlines = [TestCaseInline, CodeTemplateInline, EditorialInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('problem_number', 'title', 'slug', 'difficulty', 'is_active')
        }),
        ('Problem Content', {
            'fields': ('description', 'constraints')
        }),
        ('Examples', {
            'fields': ('example_input', 'example_output', 'example_explanation')
        }),
        ('Additional Information', {
            'fields': ('hints', 'time_complexity', 'space_complexity'),
            'classes': ('collapse',)
        }),
        ('Categorization', {
            'fields': ('topics', 'companies')
        }),
        ('Statistics', {
            'fields': ('total_submissions', 'total_accepted', 'acceptance_rate_display'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def difficulty_badge(self, obj):
        colors = {
            'easy': '#00b8a3',
            'medium': '#ffc01e',
            'hard': '#ef4743'
        }
        color = colors.get(obj.difficulty, '#666')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_difficulty_display()
        )
    difficulty_badge.short_description = 'Difficulty'
    
    def acceptance_rate_display(self, obj):
        rate = obj.acceptance_rate
        if rate == 0:
            return '-'
        
        # Color based on acceptance rate
        if rate >= 50:
            color = '#00b8a3'
        elif rate >= 30:
            color = '#ffc01e'
        else:
            color = '#ef4743'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    acceptance_rate_display.short_description = 'Acceptance Rate'
    
    def topic_list(self, obj):
        topics = obj.topics.all()[:3]
        if not topics:
            return '-'
        topic_names = ', '.join([t.name for t in topics])
        if obj.topics.count() > 3:
            topic_names += f' +{obj.topics.count() - 3}'
        return topic_names
    topic_list.short_description = 'Topics'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ['problem', 'order', 'is_sample', 'input_preview', 'output_preview']
    list_filter = ['is_sample', 'problem']
    search_fields = ['problem__title', 'input_data', 'expected_output']
    ordering = ['problem', 'order']
    
    def input_preview(self, obj):
        return obj.input_data[:50] + '...' if len(obj.input_data) > 50 else obj.input_data
    input_preview.short_description = 'Input'
    
    def output_preview(self, obj):
        return obj.expected_output[:50] + '...' if len(obj.expected_output) > 50 else obj.expected_output
    output_preview.short_description = 'Output'


@admin.register(CodeTemplate)
class CodeTemplateAdmin(admin.ModelAdmin):
    list_display = ['problem', 'language', 'has_solution']
    list_filter = ['language', 'problem']
    search_fields = ['problem__title']
    
    def has_solution(self, obj):
        return bool(obj.solution_code)
    has_solution.boolean = True
    has_solution.short_description = 'Has Solution'


@admin.register(Editorial)
class EditorialAdmin(admin.ModelAdmin):
    list_display = ['problem', 'has_video', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['problem__title', 'approach']
    readonly_fields = ['created_at', 'updated_at']
    
    def has_video(self, obj):
        return bool(obj.video_url)
    has_video.boolean = True
    has_video.short_description = 'Video Available'


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'problem', 'language', 
        'status_badge', 'test_results', 'created_at'
    ]
    list_filter = ['status', 'language', 'created_at', 'problem']
    search_fields = ['user__username', 'problem__title']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Submission Info', {
            'fields': ('user', 'problem', 'language', 'code')
        }),
        ('Results', {
            'fields': ('status', 'passed_test_cases', 'total_test_cases', 
                      'error_message', 'execution_time', 'memory_used')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'accepted': '#00b8a3',
            'wrong_answer': '#ef4743',
            'runtime_error': '#ff6b6b',
            'time_limit_exceeded': '#ffc01e',
            'compilation_error': '#ff8c00',
            'pending': '#999',
            'running': '#007bff',
        }
        color = colors.get(obj.status, '#666')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def test_results(self, obj):
        if obj.total_test_cases == 0:
            return '-'
        return f"{obj.passed_test_cases}/{obj.total_test_cases}"
    test_results.short_description = 'Test Cases'


@admin.register(UserProblemProgress)
class UserProblemProgressAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'problem', 'status_badge', 
        'attempts', 'last_attempted', 'first_solved'
    ]
    list_filter = ['status', 'last_attempted']
    search_fields = ['user__username', 'problem__title']
    readonly_fields = ['last_attempted']
    date_hierarchy = 'last_attempted'
    
    def status_badge(self, obj):
        colors = {
            'solved': '#00b8a3',
            'attempted': '#ffc01e',
            'not_attempted': '#999',
        }
        color = colors.get(obj.status, '#666')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


# Customize admin site header
admin.site.site_header = "MockMate Practice Admin"
admin.site.site_title = "Practice Admin"
admin.site.index_title = "Welcome to Practice Management"