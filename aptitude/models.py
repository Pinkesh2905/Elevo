from django.db import models
from django.contrib.auth.models import User

class AptitudeCategory(models.Model):
    """
    Broad categories like Quantitative Aptitude, Logical Reasoning, Verbal Ability, etc.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Aptitude Categories"

    def __str__(self):
        return self.name


class AptitudeTopic(models.Model):
    """
    Topics inside each category, e.g., in Quantitative Aptitude -> Profit & Loss, Time & Work.
    """
    category = models.ForeignKey(AptitudeCategory, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ("category", "name")
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.category.name} - {self.name}"


class AptitudeProblem(models.Model):
    """
    Aptitude problems (MCQs, puzzles, etc.)
    """
    topic = models.ForeignKey(AptitudeTopic, on_delete=models.CASCADE, related_name="problems")
    question_text = models.TextField()
    option_a = models.CharField(max_length=300)
    option_b = models.CharField(max_length=300)
    option_c = models.CharField(max_length=300)
    option_d = models.CharField(max_length=300)
    correct_option = models.CharField(
        max_length=1,
        choices=[('A', 'Option A'), ('B', 'Option B'),
                 ('C', 'Option C'), ('D', 'Option D')]
    )
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=10,
        choices=[("Easy", "Easy"), ("Medium", "Medium"), ("Hard", "Hard")],
        default="Medium"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Problem in {self.topic.name} [{self.difficulty}]"


class AptitudeSubmission(models.Model):
    """
    Stores user submissions for tracking performance.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="aptitude_submissions")
    problem = models.ForeignKey(AptitudeProblem, on_delete=models.CASCADE, related_name="submissions")
    selected_option = models.CharField(max_length=1, blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.selected_option:
            self.is_correct = (self.selected_option == self.problem.correct_option)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} -> {self.problem.id} ({'Correct' if self.is_correct else 'Wrong'})"


class PracticeSet(models.Model):
    """
    Custom sets of aptitude problems for practice (like quizzes/tests).
    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    problems = models.ManyToManyField(AptitudeProblem, related_name="practice_sets")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_questions(self):
        return self.problems.count()

    def __str__(self):
        return self.title


class AptitudeQuizAttempt(models.Model):
    """
    Stores a single timed aptitude quiz run for a user.
    """
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("expired", "Expired"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="aptitude_quiz_attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    question_ids = models.JSONField(default=list, blank=True)
    total_questions = models.PositiveIntegerField(default=0)
    attempted_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    score_percent = models.FloatField(default=0.0)
    achievement_label = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} quiz {self.id} ({self.status})"


class AptitudeQuizResponse(models.Model):
    """
    Stores each question response for a quiz attempt.
    """
    attempt = models.ForeignKey(AptitudeQuizAttempt, on_delete=models.CASCADE, related_name="responses")
    problem = models.ForeignKey(AptitudeProblem, on_delete=models.CASCADE, related_name="quiz_responses")
    selected_option = models.CharField(max_length=1, blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("attempt", "problem")

    def save(self, *args, **kwargs):
        if self.selected_option:
            self.is_correct = (self.selected_option == self.problem.correct_option)
        else:
            self.is_correct = False
        super().save(*args, **kwargs)
