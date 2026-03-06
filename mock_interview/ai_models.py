"""
AI usage tracking models for cost monitoring and quota enforcement.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AIUsageLog(models.Model):
    """
    Immutable log of every AI provider call for cost/latency monitoring.
    """
    PROVIDER_CHOICES = [
        ('gemini', 'Gemini'),
        ('openai', 'OpenAI'),
        ('fallback', 'Fallback'),
    ]
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('fallback', 'Fallback'),
        ('quota_exceeded', 'Quota Exceeded'),
    ]
    OPERATION_CHOICES = [
        ('resume_parse', 'Resume Parse'),
        ('question', 'Question Generation'),
        ('closing', 'Closing Message'),
        ('feedback', 'Feedback Generation'),
        ('turn_repair', 'Turn Repair'),
        ('hints', 'Interview Hints'),
        ('practice', 'Practice Question'),
        ('health_check', 'Health Check'),
        ('unknown', 'Unknown'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_usage_logs',
    )
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ai_usage_logs',
    )

    provider = models.CharField(max_length=15, choices=PROVIDER_CHOICES)
    model_name = models.CharField(max_length=80, blank=True)
    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES, default='unknown')

    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    latency_ms = models.PositiveIntegerField(default=0, help_text="Wall-clock time in milliseconds")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['operation', 'created_at']),
            models.Index(fields=['provider', 'status']),
        ]
        verbose_name = "AI Usage Log"
        verbose_name_plural = "AI Usage Logs"

    def __str__(self):
        return f"{self.operation} via {self.provider} — {self.status} ({self.created_at:%Y-%m-%d %H:%M})"
