from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, arg):
    """
    Adds a CSS class to a form field.
    Usage: {{ field|add_class:"my-class" }}
    """
    if not hasattr(value, "field") or not hasattr(value.field, "widget"):
        return value

    widget = value.field.widget
    attrs = dict(getattr(widget, "attrs", {}))
    existing = attrs.get("class", "")
    attrs["class"] = f"{existing} {arg}".strip() if existing else arg
    widget.attrs = attrs
    return value

@register.filter(name='add_attr')
def add_attr(field, css):
    """
    Adds an HTML attribute to a form field.
    Usage: {{ field|add_attr:"placeholder:Enter your text" }}
    """
    if not hasattr(field, "field") or not hasattr(field.field, "widget"):
        return field

    attrs = {}
    definitions = [entry.strip() for entry in css.split(',') if entry.strip()]
    for d in definitions:
        if '=' in d:
            key, value = d.split('=', 1)
            attrs[key.strip()] = value.strip()
        elif ':' in d:
            key, value = d.split(':', 1)
            attrs[key.strip()] = value.strip()
        else:
            attrs[d] = True

    widget = field.field.widget
    existing = dict(getattr(widget, "attrs", {}))
    existing.update(attrs)
    widget.attrs = existing
    return field

@register.filter
def split(value, delimiter):
    """Split a string by delimiter"""
    if value:
        return value.split(delimiter)
    return []

@register.filter
def trim_whitespace(value):
    """
    Removes leading and trailing whitespace from a string.
    """
    if isinstance(value, str):
        return value.strip()
    return value
