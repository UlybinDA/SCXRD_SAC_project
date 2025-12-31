from django import template

register = template.Library()

@register.filter
def bootstrap_alert_class(message_tag):
    alert_classes = {
        'debug': 'secondary',
        'info': 'info',
        'success': 'success',
        'warning': 'warning',
        'error': 'danger',  # Django использует 'error', Bootstrap - 'danger'
    }
    return alert_classes.get(message_tag, 'info')