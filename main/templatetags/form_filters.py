from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})

@register.filter(name='add_placeholder')
def add_placeholder(field, placeholder_text):
    return field.as_widget(attrs={"placeholder": placeholder_text})

@register.filter(name='add_attrs')
def add_attrs(field, args):
    attrs = {}
    for arg in args.split(','):
        key, value = arg.split(':')
        attrs[key.strip()] = value.strip()
    return field.as_widget(attrs=attrs)
