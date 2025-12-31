from django import template

register = template.Library()

@register.simple_tag
def list_proc_statuses():
    """Форматирует значение ProcStatus в строку 'код - описание'"""
    from probe.models import Probe
    fields  = Probe.ProcStatus.choices
    str_output = ''
    for field in fields:
        str_output += f"{field[0]} - {field[1]}<br>"
    return str_output