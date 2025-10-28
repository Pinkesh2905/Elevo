# mock_interview/templatetags/custom_filters.py

from django import template
from django.template.defaultfilters import stringfilter
import json
import re

register = template.Library()

# ============================================
# String Manipulation Filters
# ============================================

@register.filter(name='split')
@stringfilter
def split(value, delimiter=','):
    """
    Split a string by delimiter and return a list.
    Usage: {{ "apple,banana,cherry"|split:"," }}
    """
    if not value:
        return []
    return [item.strip() for item in value.split(delimiter) if item.strip()]

@register.filter(name='trim_whitespace')
@stringfilter
def trim_whitespace(value):
    """
    Remove leading and trailing whitespace from a string.
    Usage: {{ "  hello world  "|trim_whitespace }}
    """
    return value.strip() if value else ""

@register.filter(name='truncate_smart')
def truncate_smart(value, length=100):
    """
    Truncate text at word boundaries, not mid-word.
    Usage: {{ long_text|truncate_smart:50 }}
    """
    if not value or len(value) <= length:
        return value
    
    truncated = value[:length]
    # Find the last space to avoid cutting words
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + "..."

# ============================================
# Dictionary and JSON Filters
# ============================================

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a variable key.
    Usage: {{ mydict|get_item:dynamic_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter(name='parse_json')
def parse_json(value):
    """
    Parse a JSON string to Python object.
    Usage: {{ json_string|parse_json }}
    """
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        return None

# ============================================
# Number and Math Filters
# ============================================

@register.filter(name='percentage')
def percentage(value, total):
    """
    Calculate percentage of value relative to total.
    Usage: {{ score|percentage:100 }}
    """
    try:
        return round((float(value) / float(total)) * 100, 1) if total != 0 else 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter(name='multiply')
def multiply(value, arg):
    """
    Multiply two values.
    Usage: {{ score|multiply:3.6 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='divide')
def divide(value, arg):
    """
    Divide two values.
    Usage: {{ total|divide:count }}
    """
    try:
        return float(value) / float(arg) if float(arg) != 0 else 0
    except (ValueError, TypeError):
        return 0

@register.filter(name='format_number')
def format_number(value):
    """
    Format number with appropriate suffixes (K, M, B).
    Usage: {{ 1500|format_number }} -> "1.5K"
    """
    try:
        num = float(value)
        if abs(num) >= 1000000000:
            return f"{num/1000000000:.1f}B"
        elif abs(num) >= 1000000:
            return f"{num/1000000:.1f}M"
        elif abs(num) >= 1000:
            return f"{num/1000:.1f}K"
        else:
            return str(int(num)) if num.is_integer() else f"{num:.1f}"
    except (ValueError, TypeError):
        return str(value)

# ============================================
# Time and Duration Filters
# ============================================

@register.filter(name='duration_format')
def duration_format(seconds):
    """
    Format duration in seconds to human-readable format.
    Usage: {{ 3661|duration_format }} -> "1h 1m 1s"
    """
    try:
        seconds = int(float(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")
        
        return " ".join(parts)
    except (ValueError, TypeError):
        return "0s"

@register.filter(name='time_ago')
def time_ago(value):
    """
    Format datetime to human-readable 'time ago' format.
    Usage: {{ created_at|time_ago }}
    """
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        
        now = timezone.now()
        if value.tzinfo is None:
            value = timezone.make_aware(value)
        
        diff = now - value
        
        if diff.days > 7:
            return value.strftime('%b %d, %Y')
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    except (ValueError, TypeError, AttributeError):
        return str(value)

# ============================================
# Scoring and Assessment Filters
# ============================================

@register.filter(name='score_grade')
def score_grade(score):
    """
    Convert numeric score to letter grade.
    Usage: {{ 85|score_grade }} -> "B+"
    """
    try:
        score = float(score)
        if score >= 97:
            return "A+"
        elif score >= 93:
            return "A"
        elif score >= 90:
            return "A-"
        elif score >= 87:
            return "B+"
        elif score >= 83:
            return "B"
        elif score >= 80:
            return "B-"
        elif score >= 77:
            return "C+"
        elif score >= 73:
            return "C"
        elif score >= 70:
            return "C-"
        elif score >= 67:
            return "D+"
        elif score >= 65:
            return "D"
        else:
            return "F"
    except (ValueError, TypeError):
        return "N/A"

@register.filter(name='confidence_level')
def confidence_level(score):
    """
    Convert numeric confidence score to descriptive level.
    Usage: {{ 85|confidence_level }} -> "High"
    """
    try:
        score = float(score)
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "High"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 50:
            return "Developing"
        else:
            return "Needs Improvement"
    except (ValueError, TypeError):
        return "Unknown"

# ============================================
# UI and Styling Filters
# ============================================

@register.filter(name='status_badge')
def status_badge(status):
    """
    Get appropriate badge class for status.
    Usage: {{ interview.status|status_badge }}
    """
    status_classes = {
        'STARTED': 'badge-warning',
        'COMPLETED': 'badge-success',
        'REVIEWED': 'badge-info',
        'PENDING': 'badge-secondary',
        'CANCELLED': 'badge-danger',
    }
    return status_classes.get(status, 'badge-secondary')

@register.filter(name='skill_color')
def skill_color(skill):
    """
    Assign color class based on skill type for better UI.
    Usage: {{ skill|skill_color }}
    """
    skill_lower = skill.lower().strip()
    
    # Technical skills
    tech_skills = ['python', 'javascript', 'java', 'react', 'django', 'node.js', 'sql', 'html', 'css']
    if any(tech in skill_lower for tech in tech_skills):
        return 'skill-tech'
    
    # Soft skills
    soft_skills = ['communication', 'leadership', 'teamwork', 'management', 'problem-solving']
    if any(soft in skill_lower for soft in soft_skills):
        return 'skill-soft'
    
    # Design skills
    design_skills = ['design', 'ui', 'ux', 'photoshop', 'illustrator', 'figma']
    if any(design in skill_lower for design in design_skills):
        return 'skill-design'
    
    return 'skill-default'

# ============================================
# Utility Filters
# ============================================

@register.filter(name='default_if_none_or_empty')
def default_if_none_or_empty(value, default):
    """
    Return default if value is None, empty string, or empty list.
    Usage: {{ value|default_if_none_or_empty:"N/A" }}
    """
    if value is None or value == '' or (isinstance(value, (list, dict)) and len(value) == 0):
        return default
    return value

# ============================================
# Simple Tags
# ============================================

@register.simple_tag
def interview_progress_color(current, total):
    """
    Get color based on interview progress.
    Usage: {% interview_progress_color current_question total_questions %}
    """
    try:
        progress = (current / total) * 100
        if progress < 30:
            return "#ef4444"  # Red
        elif progress < 70:
            return "#f59e0b"  # Amber
        else:
            return "#10b981"  # Green
    except (ValueError, TypeError, ZeroDivisionError):
        return "#6b7280"  # Gray

@register.simple_tag
def skill_icon(skill):
    """
    Get appropriate icon for a skill.
    Usage: {% skill_icon "Python" %}
    """
    skill_lower = skill.lower().strip()
    
    icon_map = {
        'python': 'fab fa-python',
        'javascript': 'fab fa-js-square',
        'react': 'fab fa-react',
        'node.js': 'fab fa-node-js',
        'html': 'fab fa-html5',
        'css': 'fab fa-css3-alt',
        'git': 'fab fa-git-alt',
        'github': 'fab fa-github',
        'docker': 'fab fa-docker',
        'aws': 'fab fa-aws',
        'communication': 'fas fa-comments',
        'leadership': 'fas fa-users',
        'management': 'fas fa-tasks',
        'design': 'fas fa-palette',
        'analytics': 'fas fa-chart-line',
        'database': 'fas fa-database',
    }
    
    # Check for exact matches first
    for key, icon in icon_map.items():
        if key in skill_lower:
            return icon
    
    # Default icon
    return 'fas fa-cog'

# mock_interview/templatetags/custom_filters.py
from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter(name='split')
def split(value, arg):
    """Split a string by the given delimiter."""
    if value:
        return value.split(arg)
    return []

@register.filter(name='trim_whitespace')
def trim_whitespace(value):
    """Remove leading and trailing whitespace."""
    if value:
        return value.strip()
    return ''

@register.filter(name='multiply')
def multiply(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='parse_json')
def parse_json(value):
    """Parse JSON string into Python object."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get item from dictionary by key."""
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter(name='percentage')
def percentage(value):
    """Format a number as percentage."""
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "N/A"

@register.filter(name='format_duration')
def format_duration(minutes):
    """Format duration in minutes to human-readable format."""
    try:
        minutes = float(minutes)
        if minutes < 1:
            return f"{int(minutes * 60)} seconds"
        elif minutes < 60:
            return f"{int(minutes)} min"
        else:
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            return f"{hours}h {mins}min"
    except (ValueError, TypeError):
        return "N/A"