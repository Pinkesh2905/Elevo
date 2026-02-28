from django import template

register = template.Library()


@register.filter(name="split")
def split(value, delimiter=","):
    if not value:
        return []
    return [item.strip() for item in str(value).split(delimiter) if item.strip()]


@register.filter(name="trim_whitespace")
def trim_whitespace(value):
    return str(value).strip() if value is not None else ""


@register.filter(name="multiply")
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter(name="subtract_percentage")
def subtract_percentage(total, score):
    try:
        total = float(total)
        score = float(score)
        return total * (1 - score / 100)
    except (TypeError, ValueError):
        return total


@register.filter(name="replace")
def replace(value, arg):
    """
    Usage: {{ my_string|replace:"old,new" }}
    """
    if not value:
        return ""
    try:
        old, new = arg.split(",")
        return str(value).replace(old, new)
    except ValueError:
        return value
