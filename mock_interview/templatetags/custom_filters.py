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
