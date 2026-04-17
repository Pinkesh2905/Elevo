from django.db import models
from django.contrib.auth.models import User
from organizations.models import Organization
from practice.models import Problem as CodingProblem
from aptitude.models import AptitudeProblem

class Cohort(models.Model):
    """
    A named group of users within an organization, allowing bulk assignment.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='cohorts')
    name = models.CharField(max_length=200, help_text="e.g., 'CS Class of 2026', 'Q1 New Hires'")
    description = models.TextField(blank=True)
    members = models.ManyToManyField(User, related_name='cohorts', blank=True, help_text="Students in this specific cohort.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('organization', 'name')
        
    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class Assessment(models.Model):
    """
    A defined test/exam template combining coding problems and aptitude questions.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text="Instructions for the test taker.")
    
    # Test strictness configurations
    duration_minutes = models.PositiveIntegerField(default=60, help_text="Test duration in minutes.")
    enable_proctoring = models.BooleanField(default=True, help_text="Track tab-switches and require full-screen.")
    
    # M2M links to questions
    coding_problems = models.ManyToManyField(CodingProblem, related_name='assessments', blank=True)
    aptitude_problems = models.ManyToManyField(AptitudeProblem, related_name='assessments', blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.organization.name}"


class AssessmentAssignment(models.Model):
    """
    Assigns an Assessment to a specific Cohort with a specific availability window.
    """
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='assignments')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='assignments')
    
    start_window = models.DateTimeField(help_text="When students can start taking the test.")
    end_window = models.DateTimeField(help_text="When the test becomes completely unavailable.")
    
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_window']
        
    def __str__(self):
        return f"{self.assessment.title} -> {self.cohort.name}"


class AssessmentAttempt(models.Model):
    """
    A student's attempt to take an assigned assessment.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending (Not Started)'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUBMITTED', 'Submitted'),
        ('AUTO_SUBMITTED', 'Auto-submitted (Time Expired)'),
        ('VIOLATION_BLOCKED', 'Blocked due to proctoring violation'),
    ]
    
    assignment = models.ForeignKey(AssessmentAssignment, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assessment_attempts')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    start_time = models.DateTimeField(null=True, blank=True)
    submit_time = models.DateTimeField(null=True, blank=True)
    
    # Aggregate scores evaluated upon submission
    aptitude_score = models.FloatField(default=0, help_text="Pre-calculated aptitude score")
    coding_score = models.FloatField(default=0, help_text="Pre-calculated coding score")
    total_score = models.FloatField(default=0)
    
    # Proctoring flags tracked client-side
    tab_switch_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-start_time']
        unique_together = ('assignment', 'user')
        
    def __str__(self):
        return f"{self.user.username} attempt for {self.assignment.assessment.title}"

class ProctoringLog(models.Model):
    """
    Granular log of suspicious activity during an attempt.
    """
    EVENT_TYPE_CHOICES = [
        ('BLUR', 'Window Lost Focus / Tab Switch'),
        ('EXIT_FULL_SCREEN', 'Exited Full Screen Mode'),
        ('COPY_PASTE', 'Attempted Copy/Paste'),
        ('WEBCAM_SNAPSHOT', 'Webcam Snapshot'),
    ]
    
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name='proctoring_logs')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, help_text="Extra details regarding the violation.")
    snapshot = models.ImageField(upload_to='proctoring_snapshots/', null=True, blank=True, help_text="WebRTC snapshot capture")
    
    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} at {self.timestamp} for attempt {self.attempt.id}"
