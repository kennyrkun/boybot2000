import re
from datetime import datetime, timedelta

def _parse_time(time_str: str):
    t = time_str.strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2}):(\d{2})(am|pm)?$", t) or re.match(r"^(\d{2})(\d{2})(am|pm)?$", t)
    if not m:
        raise ValueError("Time must be HH:MM (24h), HHMM, or h:mma/pm.")
    hh, mi, ampm = m.groups()
    hh, mi = int(hh), int(mi)
    if ampm:
        hh = (hh % 12) + (12 if ampm == "pm" else 0)
    if not (0 <= hh <= 23 and 0 <= mi <= 59):
        raise ValueError("Invalid time.")
    return hh, mi

def _next_run(now: datetime, hh: int, mi: int, cadence: str) -> datetime:
    target = now.replace(hour=hh, minute=mi, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1 if cadence == "daily" else 7)
    return target