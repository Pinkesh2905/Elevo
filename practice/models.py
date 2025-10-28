from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator


class Topic(models.Model):
    """Topics/Tags for problems (e.g., Arrays, Dynamic Programming, Trees)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Company(models.Model):
    """Companies that ask these problems in interviews"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    website = models.URLField(blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Companies"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Problem(models.Model):
    """Main coding problem model (LeetCode-style)"""
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    # Basic Info
    problem_number = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    
    # Content
    description = models.TextField(help_text="Problem statement in HTML or Markdown")
    constraints = models.TextField(blank=True, help_text="Problem constraints")
    
    # Examples
    example_input = models.TextField(blank=True, help_text="Example input")
    example_output = models.TextField(blank=True, help_text="Example output")
    example_explanation = models.TextField(blank=True, help_text="Explanation for example")
    
    # Additional Info
    hints = models.TextField(blank=True, help_text="Hints (one per line or JSON)")
    time_complexity = models.CharField(max_length=50, blank=True, help_text="e.g., O(n log n)")
    space_complexity = models.CharField(max_length=50, blank=True, help_text="e.g., O(n)")
    
    # Relationships
    topics = models.ManyToManyField(Topic, related_name='problems', blank=True)
    companies = models.ManyToManyField(Company, related_name='problems', blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_problems')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Stats (can be updated periodically)
    total_submissions = models.PositiveIntegerField(default=0)
    total_accepted = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['problem_number']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.problem_number}-{self.title}")
        super().save(*args, **kwargs)
    
    @property
    def acceptance_rate(self):
        if self.total_submissions == 0:
            return 0
        return round((self.total_accepted / self.total_submissions) * 100, 1)
    
    def __str__(self):
        return f"{self.problem_number}. {self.title}"


class TestCase(models.Model):
    """Test cases for problems"""
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField(help_text="Input for the test case")
    expected_output = models.TextField(help_text="Expected output")
    is_sample = models.BooleanField(default=False, help_text="Show this test case to users?")
    explanation = models.TextField(blank=True, help_text="Explanation for this test case")
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    class Meta:
        ordering = ['problem', 'order']
    
    def __str__(self):
        return f"TestCase #{self.order} for {self.problem.title}"


class CodeTemplate(models.Model):
    """Starter code templates for different languages"""
    
    LANGUAGE_CHOICES = [
        ('python3', 'Python 3'),
        ('cpp17', 'C++ 17'),
        ('java', 'Java'),
        ('javascript', 'JavaScript'),
        ('c', 'C'),
        ('csharp', 'C#'),
        ('go', 'Go'),
        ('rust', 'Rust'),
    ]
    
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='code_templates')
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES)
    template_code = models.TextField(help_text="Starter code shown to users")
    solution_code = models.TextField(blank=True, help_text="Reference solution (hidden from users)")
    
    class Meta:
        unique_together = ['problem', 'language']
        ordering = ['problem', 'language']
    
    def __str__(self):
        return f"{self.get_language_display()} template for {self.problem.title}"


class Editorial(models.Model):
    """Editorial/solution explanation for problems"""
    problem = models.OneToOneField(Problem, on_delete=models.CASCADE, related_name='editorial')
    approach = models.TextField(help_text="Solution approach explanation")
    complexity_analysis = models.TextField(blank=True, help_text="Time and space complexity analysis")
    code_explanation = models.TextField(blank=True, help_text="Line-by-line code explanation")
    video_url = models.URLField(blank=True, help_text="YouTube or other video explanation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Editorial for {self.problem.title}"


class Submission(models.Model):
    """User code submissions"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('accepted', 'Accepted'),
        ('wrong_answer', 'Wrong Answer'),
        ('runtime_error', 'Runtime Error'),
        ('time_limit_exceeded', 'Time Limit Exceeded'),
        ('compilation_error', 'Compilation Error'),
    ]
    
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    code = models.TextField()
    language = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Results
    passed_test_cases = models.PositiveIntegerField(default=0)
    total_test_cases = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    execution_time = models.FloatField(null=True, blank=True, help_text="Execution time in milliseconds")
    memory_used = models.FloatField(null=True, blank=True, help_text="Memory used in MB")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.problem.title} ({self.status})"


class UserProblemProgress(models.Model):
    """Track user progress on problems"""
    
    STATUS_CHOICES = [
        ('not_attempted', 'Not Attempted'),
        ('attempted', 'Attempted'),
        ('solved', 'Solved'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='problem_progress')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='user_progress')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_attempted')
    attempts = models.PositiveIntegerField(default=0)
    last_attempted = models.DateTimeField(auto_now=True)
    first_solved = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'problem']
        ordering = ['-last_attempted']
    
    def __str__(self):
        return f"{self.user.username} - {self.problem.title} ({self.status})"