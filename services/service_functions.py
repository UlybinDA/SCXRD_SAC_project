
def hours_to_str_time(hours, round_digits=0, val_only=False):
    hours_int = int(hours)
    minutes = (hours - hours_int) * 60
    
    if round_digits == 0:
        minutes_int = int(round(minutes))
    else:
        minutes_int = round(minutes, round_digits)
    

    if minutes_int >= 60:
        hours_int += int(minutes_int // 60)
        minutes_int = minutes_int % 60
    
    if round_digits == 0:
        minutes_str = f"{int(minutes_int):02d}"
    else:
        minutes_str = f"{minutes_int:05.2f}".rstrip('0').rstrip('.')

    if val_only:
        return f"{hours_int:02d}", minutes_str
    
    return f"{hours_int:02d} ч. {minutes_str} мин."
