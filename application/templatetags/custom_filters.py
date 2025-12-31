from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу"""
    return dictionary.get(key, '')


@register.filter
def format_proc_status(value):
    """Форматирует значение ProcStatus в строку 'код - описание'"""
    if not value:
        return ""

    from probe.models import Probe  # Импортируем здесь чтобы избежать циклического импорта
    for code, description in Probe.ProcStatus.choices:
        if code == value:
            return f"{code} - {description}"
    return value

