from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator

from .ai_models import AIUsageLog  # noqa: F401 — discovered by migrations

class MockInterviewSession(models.Model):
    """
    Represents a single mock interview session taken by a user.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mock_interview_sessions')

    # Resume upload (optional)
    resume_file = models.FileField(
        upload_to='mock_interviews/resumes/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx'])],
        help_text="Upload your resume in PDF or DOCX format."
    )

    extracted_resume_text = models.TextField(
        blank=True,
        null=True,
        help_text="Raw extracted text from uploaded resume (for internal use)."
    )

    parsed_resume_data = models.JSONField(
        blank=True,
        null=True,
        help_text="Structured JSON extracted from resume via AI (job_role, skills, etc.)."
    )

    # Manual entry fallback if no resume
    job_role = models.CharField(max_length=255, blank=True, help_text="Target job role for the interview.")
    key_skills = models.TextField(blank=True, help_text="Comma-separated key skills provided by the user.")

    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)

    SESSION_STATUS_CHOICES = [
        ('STARTED', 'Started'),
        ('FEEDBACK_PROCESSING', 'Feedback Processing'),
        ('COMPLETED', 'Completed'),
        ('REVIEW_PENDING', 'Review Pending'),
        ('REVIEWED', 'Reviewed'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=SESSION_STATUS_CHOICES,
        default='STARTED',
        help_text="Current status of the mock interview session."
    )

    overall_feedback = models.TextField(blank=True, null=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                help_text="Overall score for the interview (e.g., 0-100).")
                                
    # AI Voice Metrics & Rubrics
    RUBRIC_CHOICES = [
        ('faang', 'FAANG Rubric (SDE/MAANG)'),
        ('service', 'Service Based Rubric (TCS/Infosys)'),
        ('general', 'General Rubric'),
    ]
    rubric_type = models.CharField(max_length=20, choices=RUBRIC_CHOICES, default='general')
    
    # FAANG Metrics
    problem_solving_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    code_quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    system_design_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Service Metrics
    oops_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    dbms_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    core_cs_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    sentiment_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Overall communication and professional sentiment score.")

    PERFORMANCE_BAND_CHOICES = [
        ('foundation', 'Foundation'),
        ('standard', 'Standard'),
        ('advanced', 'Advanced'),
    ]
    performance_band = models.CharField(
        max_length=20,
        choices=PERFORMANCE_BAND_CHOICES,
        default='standard',
        help_text="Current adaptive performance band.",
    )
    starting_band = models.CharField(
        max_length=20,
        choices=PERFORMANCE_BAND_CHOICES,
        default='standard',
        help_text="Initial adaptive performance band at session start.",
    )
    current_band = models.CharField(
        max_length=20,
        choices=PERFORMANCE_BAND_CHOICES,
        default='standard',
        help_text="Latest adaptive performance band based on turn progression.",
    )
    band_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50.00,
        help_text="Confidence (0-100) in current adaptive band assignment.",
    )
    weak_skill_tags = models.JSONField(default=list, blank=True)
    strong_skill_tags = models.JSONField(default=list, blank=True)
    selected_pack = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Selected interview pack preset identifier.",
    )
    feedback_status = models.CharField(
        max_length=20,
        default="pending",
        help_text="Feedback generation lifecycle: pending, processing, ready, failed.",
    )
    feedback_error = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Mock Interview Session"
        verbose_name_plural = "Mock Interview Sessions"

    def __str__(self):
        return f"{self.user.username}'s interview for {self.job_role or 'Unknown Role'} ({self.status})"


class InterviewTurn(models.Model):
    """
    Stores each question-answer turn within a mock interview session.
    """
    session = models.ForeignKey(MockInterviewSession, on_delete=models.CASCADE, related_name='turns')
    turn_number = models.PositiveIntegerField(help_text="Order of this turn in the interview.")

    ai_question = models.TextField(help_text="The question asked by the AI.")
    user_answer = models.TextField(blank=True, null=True, help_text="The user's transcribed answer.")

    ai_internal_analysis = models.TextField(blank=True, null=True, help_text="AI's internal assessment of the user's answer.")
    ai_follow_up_feedback = models.TextField(blank=True, null=True, help_text="AI's direct feedback or next question.")
    DIFFICULTY_LEVEL_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    difficulty_level = models.CharField(
        max_length=10,
        choices=DIFFICULTY_LEVEL_CHOICES,
        default='medium',
        help_text="Difficulty of this turn's generated question.",
    )
    skill_tags = models.JSONField(default=list, blank=True)
    turn_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    communication_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    technical_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    band_after_turn = models.CharField(
        max_length=20,
        choices=MockInterviewSession.PERFORMANCE_BAND_CHOICES,
        default='standard',
        help_text="Adaptive band after evaluating this turn.",
    )

    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['turn_number']
        unique_together = ('session', 'turn_number')
        verbose_name = "Interview Turn"
        verbose_name_plural = "Interview Turns"

    def __str__(self):
        return f"Turn {self.turn_number} of {self.session.user.username}'s {self.session.job_role or 'Unknown Role'} interview"
